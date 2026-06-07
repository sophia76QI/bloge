"""
newsletter_writer.py - PHASE 3 (병렬): Newsletter Writer Agent (Sonnet)

Reads output/blog_reviewed.md, writes output/newsletter.md.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
너는 다빈치힐스 뉴스레터 에디터다.
블로그 원고를 읽고 뉴스레터 형식으로 재편집한다.

[형식]
- 제목: 이메일 오픈율을 높이는 후킹 제목 (40자 이내)
- 도입: 2~3문장 핵심 요약 (독자가 읽을 이유)
- 본문: 핵심 종목 3개, 각각 확신도%·근거·반증 1줄씩
- 마무리: 다음 뉴스레터 예고 1문장
- 하단: 면책 조항 (원문 그대로)
- 길이: 400~600자

톤: 친근+전문, 단정 금지
""".strip()


def run(output_dir: str = "output", max_tokens: int = 2048) -> Path:
    out_path = Path(output_dir)
    reviewed_file = out_path / "blog_reviewed.md"
    newsletter_file = out_path / "newsletter.md"

    if not reviewed_file.exists():
        raise FileNotFoundError(f"blog_reviewed.md not found at {reviewed_file}")

    content = reviewed_file.read_text(encoding="utf-8")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("[Newsletter Writer] Calling Claude Sonnet...")
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"아래 블로그 원고를 뉴스레터로 변환해주세요:\n\n{content}"}],
            )
            result = message.content[0].text if message.content else _template_fallback(content)
            newsletter_file.write_text(result, encoding="utf-8")
            logger.info(f"[Newsletter Writer] ✅ newsletter.md written ({len(result)} chars)")
            return newsletter_file
        except Exception as e:
            logger.error(f"[Newsletter Writer] LLM failed: {e}, using template")

    result = _template_fallback(content)
    newsletter_file.write_text(result, encoding="utf-8")
    logger.info("[Newsletter Writer] ✅ newsletter.md written (template)")
    return newsletter_file


def _template_fallback(blog_content: str) -> str:
    lines = blog_content.split("\n")
    title_line = next((l for l in lines if l.startswith("# ")), "외국인 순매수 셜록홈즈 리포트")
    title = title_line.lstrip("# ").strip()
    excerpt = " ".join(l.strip() for l in lines[2:8] if l.strip())[:200]

    disclaimer = """
---
⚠️ 면책 조항: 본 콘텐츠는 KRX·DART 공개 데이터 기반 수급 추리입니다.
투자 권유 또는 위법 단정이 아니며, 최종 판단은 본인 책임입니다.
© 다빈치힐스 · 외국인 순매수 셜록홈즈 v1.0
""".strip()

    return f"""# 📬 {title}

{excerpt}...

> 전체 분석은 블로그에서 확인하세요.

{disclaimer}
"""
