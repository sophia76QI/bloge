"""
reviewer.py - PHASE 2: Reviewer Agent (Sonnet)

Reads output/blog.md, writes output/blog_reviewed.md.
품질 검수 · 개선 — 면책·출처위계·가설형식 체크리스트 기반.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
너는 다빈치힐스 콘텐츠 품질 검수 전문가다.
블로그 원고를 읽고 아래 체크리스트를 통과하도록 개선한 뒤 최종본을 출력한다.

[품질 체크리스트]
- [ ] 결론이 "확신도 % 가설"인가? (판정 표현 금지)
- [ ] 기업·기관 위법 단정 표현이 없는가?
- [ ] 모든 수치에 출처 위계 [1차/2차/3차/추측]가 있는가?
- [ ] 모든 데이터에 기준일(as_of_date)이 명시됐는가?
- [ ] "이 가설이 틀렸다면?" 반증 시나리오가 있는가?
- [ ] 면책 조항이 하단에 있는가?
- [ ] 다빈치힐스 톤(친근+전문, 단정 금지)이 유지되는가?
- [ ] SEO 소제목(##)이 적절히 사용됐는가?

개선 사항을 적용한 완성본만 출력한다. 체크리스트 코멘트는 본문에 넣지 않는다.
""".strip()


def run(
    output_dir: str = "output",
    max_tokens: int = 4096,
) -> Path:
    """
    Review blog.md and write blog_reviewed.md.
    Falls back to copying blog.md if ANTHROPIC_API_KEY is not set.
    """
    out_path = Path(output_dir)
    blog_file = out_path / "blog.md"
    reviewed_file = out_path / "blog_reviewed.md"

    if not blog_file.exists():
        raise FileNotFoundError(f"blog.md not found at {blog_file}")

    blog_content = blog_file.read_text(encoding="utf-8")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)

            logger.info("[Reviewer] Calling Claude Sonnet for review...")
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"아래 블로그 원고를 검수하고 개선된 최종본을 출력해주세요:\n\n{blog_content}",
                }],
            )
            reviewed = message.content[0].text if message.content else blog_content
            reviewed_file.write_text(reviewed, encoding="utf-8")
            logger.info(f"[Reviewer] ✅ blog_reviewed.md written ({len(reviewed)} chars)")
            return reviewed_file
        except Exception as e:
            logger.error(f"[Reviewer] LLM call failed: {e}, copying blog.md as-is")

    # Fallback: pass through
    reviewed_file.write_text(blog_content, encoding="utf-8")
    logger.info("[Reviewer] ✅ blog_reviewed.md written (passthrough)")
    return reviewed_file
