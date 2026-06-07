"""
threads_writer.py - PHASE 3 (병렬): Threads Writer Agent (Sonnet)

Reads output/blog_reviewed.md, writes output/threads.md.
4044 공식: 4개 핵심 포인트, 440자 이내 청크.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
너는 다빈치힐스 Threads(스레드) 전문 에디터다.
블로그 원고를 읽고 Threads 연속 포스팅으로 변환한다.

[4044 공식]
- 각 스레드: 440자 이내
- 총 4개 스레드 청크
  1. 후킹 첫 문장 + 오늘의 핵심 1줄
  2. 종목 1~2개 확신도%·근거 요약
  3. "이 가설이 틀렸다면?" 반증 + 노이즈 필터
  4. 면책 조항 + CTA (블로그 링크 유도)
- 스레드 구분: --- 으로 분리
- 이모지 적극 활용
- 단정 표현 금지
""".strip()


def run(output_dir: str = "output", max_tokens: int = 1024) -> Path:
    out_path = Path(output_dir)
    reviewed_file = out_path / "blog_reviewed.md"
    threads_file = out_path / "threads.md"

    if not reviewed_file.exists():
        raise FileNotFoundError(f"blog_reviewed.md not found at {reviewed_file}")

    content = reviewed_file.read_text(encoding="utf-8")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("[Threads Writer] Calling Claude Sonnet...")
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"아래 블로그 원고를 Threads 포스팅으로 변환해주세요:\n\n{content[:3000]}"}],
            )
            result = message.content[0].text if message.content else _template_fallback(content)
            threads_file.write_text(result, encoding="utf-8")
            logger.info(f"[Threads Writer] ✅ threads.md written ({len(result)} chars)")
            return threads_file
        except Exception as e:
            logger.error(f"[Threads Writer] LLM failed: {e}, using template")

    result = _template_fallback(content)
    threads_file.write_text(result, encoding="utf-8")
    logger.info("[Threads Writer] ✅ threads.md written (template)")
    return threads_file


def _template_fallback(blog_content: str) -> str:
    lines = [l.strip() for l in blog_content.split("\n") if l.strip()]
    excerpt = " ".join(lines[1:4])[:150]
    return f"""🔍 오늘 외국인이 먼저 움직인 종목이 있습니다.
공개 데이터로 '스마트머니 흔적'을 추리했어요.
(투자 권유 ❌ — 통계 가설입니다)

---

{excerpt}...

자세한 분석은 블로그에서 확인하세요 👇

---

🔄 이 가설이 틀렸다면?
→ 단순 패시브 유입 or 공매도 커버 가능성
→ 인덱스 리밸런싱에 의한 기계적 매수

---

⚠️ 투자 권유 아님 · 모든 판단은 본인 책임
© 다빈치힐스 · 외국인 순매수 셜록홈즈 v1.0
"""
