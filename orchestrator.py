"""
orchestrator.py - Main Orchestrator for 외국인 순매수 셜록홈즈

Coordinates the three specialist agents:
  1. collector  → fetch KRX/DART data for universe
  2. detective  → screen for lead-lag patterns, score hypotheses
  3. publisher  → format blog post + threads post

Usage:
  python orchestrator.py [--tickers 005930 000660 ...] [--days 20]
                         [--top-n 5] [--output-dir output]

Requires:
  .env with DART_API_KEY (optional: ANTHROPIC_API_KEY for LLM narrative)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrator")

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; rely on environment variables

# ── Default universe: 30 KOSPI blue-chips ────────────────────────────────────
DEFAULT_UNIVERSE = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "006400",  # 삼성SDI
    "035720",  # 카카오
    "003550",  # LG
    "028260",  # 삼성물산
    "066570",  # LG전자
    "009150",  # 삼성전기
    "207940",  # 삼성바이오로직스
    "068270",  # 셀트리온
    "000270",  # 기아
    "012330",  # 현대모비스
    "096770",  # SK이노베이션
    "017670",  # SK텔레콤
    "030200",  # KT
    "032830",  # 삼성생명
    "086790",  # 하나금융지주
    "105560",  # KB금융
    "055550",  # 신한지주
    "316140",  # 우리금융지주
    "024110",  # IBK기업은행
    "018260",  # 삼성SDS
    "011200",  # HMM
    "010950",  # S-Oil
    "000810",  # 삼성화재
    "032640",  # LG유플러스
    "251270",  # 넷마블
]

ORCHESTRATOR_SYSTEM = """
너는 '외국인 순매수 셜록홈즈'의 총괄 팀장이다.
3명의 전문가(수집/추리/출력)를 지휘해 매일 리드마그넷 1건을 만든다.

[절대 규칙]
1. 모든 수치에 출처 위계 [1차/2차/3차/추측]를 붙인다.
2. 데이터가 없으면 추정하지 말고 "데이터 없음"으로 표기한다. (환각 금지)
3. 결론은 "판정"이 아니라 "확신도 %를 붙인 가설"로만 출력한다.
4. 어떤 기업·기관에도 위법(내부정보 이용 등)을 단정하지 않는다.
5. 모든 데이터는 시점(기준일)을 명시한다. (예: KRX 기준 T-1 종가)

[워크플로우]
1) 수집 에이전트에게 대상 유니버스의 외국인 수급·공매도·대차·공시 데이터를 요청
2) 추리 에이전트에게 선행 매수 패턴 스크리닝 + 상위 종목 심층 추리를 요청
3) 출력 에이전트에게 리드마그넷(블로그/스레드) 변환을 요청
4) 면책 조항을 모든 산출물 하단에 강제 삽입
""".strip()


def _enhance_with_llm(
    blog_post: str,
    results: list,
) -> str:
    """
    Optionally enhance the blog post narrative using Anthropic API.
    Falls back to raw template output if ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — using template output (no LLM enhancement)")
        return blog_post

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "다음은 외국인 순매수 셜록홈즈 분석 리포트 초안입니다. "
            "다빈치힐스 브랜드 톤(친근+전문, 단정 금지)으로 자연스럽게 다듬어 주세요. "
            "수치·출처 위계·면책 조항은 절대 삭제하지 마세요. "
            "확신도 %와 '가설'이라는 표현은 반드시 유지하세요.\n\n"
            f"---\n{blog_post}"
        )

        message = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt},
            ],
            system=ORCHESTRATOR_SYSTEM,
        )
        enhanced = message.content[0].text if message.content else blog_post
        logger.info("LLM narrative enhancement complete.")
        return enhanced

    except Exception as e:
        logger.warning(f"LLM enhancement failed ({e}), using template output")
        return blog_post


def main(
    tickers: List[str] | None = None,
    days: int = 20,
    top_n: int = 5,
    output_dir: str = "output",
    z_threshold: float = 2.0,
    lookforward_days: int = 20,
    enhance_llm: bool = True,
) -> None:
    print("=" * 60)
    print("外国人 순매수 셜록홈즈 — 멀티에이전트 오케스트레이터")
    print("=" * 60)
    print(ORCHESTRATOR_SYSTEM)
    print("=" * 60)

    tickers = tickers or DEFAULT_UNIVERSE
    run_date = datetime.today().strftime("%Y%m%d_%H%M%S")
    run_date_display = datetime.today().strftime("%Y년 %m월 %d일")

    # ── STEP 1: Collect ──────────────────────────────────────────
    logger.info(f"[PHASE 1] 수집 에이전트 시작 — {len(tickers)}개 종목, {days}일")
    from agents.collector import collect_universe

    universe_data = collect_universe(tickers, days=days)
    logger.info(f"[PHASE 1] 수집 완료 — {len(universe_data)}개 종목")

    # ── STEP 2: Detect / Score ───────────────────────────────────
    logger.info(f"[PHASE 2-3] 추리 에이전트 시작 — Z>{z_threshold}, 선행 {lookforward_days}일")
    from agents.detective import screen_universe

    results = screen_universe(
        universe_data,
        z_threshold=z_threshold,
        lookforward_days=lookforward_days,
        top_n=top_n,
    )
    logger.info(f"[PHASE 2-3] 추리 완료 — 상위 {len(results)}개 종목 선별")

    # ── STEP 3: Publish ──────────────────────────────────────────
    logger.info("[PHASE 4] 출력 에이전트 시작")
    from agents.publisher import format_blog_post, format_threads_post

    blog_post = format_blog_post(results, run_date=run_date_display)
    threads_post = format_threads_post(results, run_date=datetime.today().strftime("%m/%d"))

    # Optional LLM enhancement
    if enhance_llm:
        blog_post = _enhance_with_llm(blog_post, results)

    # ── Save outputs ─────────────────────────────────────────────
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    blog_file = out_path / f"blog_{run_date}.md"
    threads_file = out_path / f"threads_{run_date}.txt"
    json_file = out_path / f"results_{run_date}.json"

    blog_file.write_text(blog_post, encoding="utf-8")
    threads_file.write_text(threads_post, encoding="utf-8")

    # Serialize results (DataFrames replaced with summaries)
    serializable = []
    for r in results:
        sr = {k: v for k, v in r.items() if not hasattr(v, "to_dict")}
        serializable.append(sr)
    json_file.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info(f"출력 완료:")
    logger.info(f"  블로그 원고  → {blog_file}")
    logger.info(f"  스레드 본문  → {threads_file}")
    logger.info(f"  분석 JSON   → {json_file}")

    # Print summary to stdout
    print("\n📊 최종 결과 요약")
    print("-" * 40)
    for r in results:
        print(
            f"  [{r['ticker']}] 확신도 {r['conviction_pct']}% — {r['hypothesis'][:50]}..."
        )
    print()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="외국인 순매수 셜록홈즈 오케스트레이터")
    parser.add_argument(
        "--tickers", nargs="+", default=None,
        help="분석할 종목 코드 (기본: DEFAULT_UNIVERSE 30종목)",
    )
    parser.add_argument("--days", type=int, default=20, help="수집 기간 (거래일 기준, 기본 20)")
    parser.add_argument("--top-n", type=int, default=5, help="출력할 상위 종목 수")
    parser.add_argument("--output-dir", default="output", help="출력 디렉토리")
    parser.add_argument("--z-threshold", type=float, default=2.0, help="Z-score 임계값")
    parser.add_argument("--lookforward", type=int, default=20, help="선행성 검증 기간(일)")
    parser.add_argument("--no-llm", action="store_true", help="LLM 내러티브 강화 비활성화")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(
        tickers=args.tickers,
        days=args.days,
        top_n=args.top_n,
        output_dir=args.output_dir,
        z_threshold=args.z_threshold,
        lookforward_days=args.lookforward,
        enhance_llm=not args.no_llm,
    )
