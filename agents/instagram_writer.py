"""
instagram_writer.py - PHASE 3 (병렬): Instagram Feed Writer Agent (Sonnet)

Reads output/blog_reviewed.md, writes output/instagram.md.
카드뉴스 캡션 + 슬라이드 구성안.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
너는 다빈치힐스 인스타그램 피드 전문 에디터다.
블로그 원고를 읽고 카드뉴스 구성안 + 캡션을 작성한다.

[카드뉴스 구성 (슬라이드 6장)]
- 슬라이드 1 (커버): 종목명 + 확신도% + 후킹 카피
- 슬라이드 2: 이상 매수 탐지 — t0 날짜 + Z-score 시각화 설명
- 슬라이드 3: 선행성 증거 — 가격 흐름 요약
- 슬라이드 4: 노이즈 필터 — "왜 단순 패시브가 아닌가?"
- 슬라이드 5: 반증 시나리오 — "이 가설이 틀렸다면?"
- 슬라이드 6: 결론 + 면책 조항

[캡션]
- 150자 이내
- 해시태그 5개 이하
- 단정 표현 금지

출력 형식:
## [슬라이드 N] 제목
본문 텍스트

## 캡션
캡션 텍스트
#해시태그
""".strip()


def run(output_dir: str = "output", max_tokens: int = 1500) -> Path:
    out_path = Path(output_dir)
    reviewed_file = out_path / "blog_reviewed.md"
    instagram_file = out_path / "instagram.md"

    if not reviewed_file.exists():
        raise FileNotFoundError(f"blog_reviewed.md not found at {reviewed_file}")

    content = reviewed_file.read_text(encoding="utf-8")
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("[Instagram Writer] Calling Claude Sonnet...")
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"아래 블로그 원고를 인스타그램 카드뉴스로 변환해주세요:\n\n{content[:3000]}"}],
            )
            result = message.content[0].text if message.content else _template_fallback(content)
            instagram_file.write_text(result, encoding="utf-8")
            logger.info(f"[Instagram Writer] ✅ instagram.md written ({len(result)} chars)")
            return instagram_file
        except Exception as e:
            logger.error(f"[Instagram Writer] LLM failed: {e}, using template")

    result = _template_fallback(content)
    instagram_file.write_text(result, encoding="utf-8")
    logger.info("[Instagram Writer] ✅ instagram.md written (template)")
    return instagram_file


def _template_fallback(blog_content: str) -> str:
    lines = [l for l in blog_content.split("\n") if l.strip()]
    title = next((l.lstrip("# ") for l in lines if l.startswith("# ")), "외국인 순매수 셜록홈즈")

    return f"""## [슬라이드 1] 커버
🔍 {title}
외국인이 먼저 움직였다? — 확신도 OO% 가설

## [슬라이드 2] 이상 매수 탐지
60일 평균 대비 Z-score 2.0 초과 탐지
→ 평소와 다른 매수 패턴 포착 [추측]

## [슬라이드 3] 선행성 증거
t0 이후 주가 +X% 이상 또는 호재 공시 확인
→ 매수가 이벤트를 '선행'했을 가능성 [2차]

## [슬라이드 4] 노이즈 필터
✅ 공매도 급증 없음
✅ 인덱스 편입 공시 없음
→ 단순 패시브 가능성 낮음 [추측]

## [슬라이드 5] 이 가설이 틀렸다면?
- 패시브 ETF 리밸런싱 기계적 매수
- 공매도 숏커버링 착시
- 배당락 기술적 매수

## [슬라이드 6] 결론 + 면책
가설 확신도 OO% — 투자 권유 아님
© 다빈치힐스 · 외국인 순매수 셜록홈즈 v1.0

## 캡션
🔍 외국인 선행 매수 추리 리포트 | 공개 데이터 기반 통계 가설입니다.
투자 권유 ❌ 모든 판단은 본인 책임
#외국인순매수 #스마트머니 #주식추리 #다빈치힐스 #셜록홈즈
"""
