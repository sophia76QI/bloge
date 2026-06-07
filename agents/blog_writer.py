"""
blog_writer.py - PHASE 1: Blog Writer Agent (Opus)

Reads detective analysis JSON, writes output/blog.md.
SEO 장문 블로그 원고 — 4-PHASE 셜록 구조.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
너는 다빈치힐스 브랜드의 SEO 전문 블로그 라이터다.
외국인 순매수 셜록홈즈 분석 결과를 바탕으로 장문 블로그 원고를 작성한다.

[규칙]
- 톤: 친근+전문, 단정 금지 ("무조건"·"100%" 사용 안 함)
- 결론은 반드시 "확신도 OO% 가설"로 표현
- 출처 위계 [1차/2차/3차/추측] 를 수치마다 표기
- 시간 지평 태그 [단기 노이즈][중기 트렌드][구조적 변화] 사용
- "이 가설이 틀렸다면?" 반증 시나리오 포함
- 면책 조항을 하단에 반드시 삽입
- 글자수 1500자 이상, SEO 소제목(##) 활용
""".strip()

DISCLAIMER = """
---
⚠️ 면책 조항

본 콘텐츠는 공개 데이터(KRX·DART)에 기반한 '수급 패턴 추리'로,
투자 권유나 특정 종목·기관의 위법 행위를 단정하는 자료가 아닙니다.
'정보 우위로 보이는 선행 매수'는 통계적 가설이며, 실제 원인은
패시브 유입·차익거래·우연일 수 있습니다.
모든 투자 결정과 판단의 책임은 본인에게 있으며,
중요한 판단은 1차 자료와 전문가 의견을 교차 확인 후 내리십시오.

© 다빈치힐스 · 백만장자 메신저 · 외국인 순매수 셜록홈즈 v1.0
""".strip()


def _build_prompt(results: List[Dict[str, Any]], run_date: str) -> str:
    top = results[:5]
    summary_lines = []
    for r in top:
        ticker = r.get("ticker", "???")
        conviction = r.get("conviction_pct", 0)
        hypothesis = r.get("hypothesis", "")
        evidence = r.get("evidence", [])
        counter = r.get("counter_scenarios", [])
        as_of = r.get("as_of_date", "")

        summary_lines.append(f"## 종목: {ticker}")
        summary_lines.append(f"- 확신도: {conviction}%")
        summary_lines.append(f"- 가설: {hypothesis}")
        summary_lines.append(f"- 기준일: {as_of}")
        if evidence:
            summary_lines.append("- 근거:")
            for ev in evidence[:5]:
                summary_lines.append(f"  - {ev}")
        if counter:
            summary_lines.append("- 반증 시나리오:")
            for cs in counter[:3]:
                summary_lines.append(f"  - {cs}")
        summary_lines.append("")

    analysis_text = "\n".join(summary_lines)

    return f"""기준일: {run_date}

아래 외국인 순매수 셜록홈즈 분석 결과를 바탕으로
SEO 최적화 장문 블로그 원고를 한국어로 작성해주세요.

4-PHASE 구조를 따르세요:
PHASE 1 수집 → PHASE 2 가설 → PHASE 3 검증 → PHASE 4 결론

--- 분석 데이터 ---
{analysis_text}
---

마지막에 아래 면책 조항을 그대로 붙여주세요:

{DISCLAIMER}
"""


def run(
    results: List[Dict[str, Any]],
    output_dir: str = "output",
    run_date: str = "",
    max_tokens: int = 4096,
) -> Path:
    """
    Generate blog.md using Claude Opus.
    Falls back to template if ANTHROPIC_API_KEY is not set.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    blog_file = out_path / "blog.md"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = _build_prompt(results, run_date)

            logger.info("[Blog Writer] Calling Claude Opus...")
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text if message.content else ""
            blog_file.write_text(content, encoding="utf-8")
            logger.info(f"[Blog Writer] ✅ blog.md written ({len(content)} chars)")
            return blog_file
        except Exception as e:
            logger.error(f"[Blog Writer] LLM call failed: {e}, falling back to template")

    # Fallback: template
    from agents.publisher import format_blog_post
    content = format_blog_post(results, run_date=run_date)
    blog_file.write_text(content, encoding="utf-8")
    logger.info(f"[Blog Writer] ✅ blog.md written via template ({len(content)} chars)")
    return blog_file
