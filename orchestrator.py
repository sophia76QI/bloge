"""
orchestrator.py - 콘텐츠 멀티에이전트 시스템 오케스트레이터

이미지 구조:
  PHASE 1 (순차)  : Blog Writer (Opus)          → output/blog.md
  PHASE 2 (순차)  : Reviewer (Sonnet)            → output/blog_reviewed.md
  PHASE 3 (병렬)  : Newsletter / Threads / IG    → output/{newsletter,threads,instagram}.md
  PHASE 4 (최종)  : Notion Uploader (Sonnet+MCP) → Notion 페이지

에이전트 간 직접 통신 없음 — output/ 공유 파일로만 연결.
단계 실행 · 산출물 검증 · 실패 시 해당 단계 재시도 · 진행 보고.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrator")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def _print_phase(n: int, label: str, mode: str = "") -> None:
    tag = f" ({mode})" if mode else ""
    print(f"\n{'='*60}")
    print(f"  PHASE {n}{tag}: {label}")
    print(f"{'='*60}")


def _verify_output(path: Path, phase: str) -> bool:
    if path.exists() and path.stat().st_size > 100:
        logger.info(f"[{phase}] ✅ {path.name} OK ({path.stat().st_size} bytes)")
        return True
    logger.warning(f"[{phase}] ⚠️ {path.name} missing or too small")
    return False


def run_phase1(results: list, output_dir: str, run_date: str, max_retries: int = 2) -> bool:
    """PHASE 1 순차: Blog Writer (Opus) → output/blog.md"""
    _print_phase(1, "Blog Writer (Opus) — SEO 장문 블로그 작성", "순차")
    from agents.blog_writer import run as blog_run

    for attempt in range(1, max_retries + 1):
        try:
            blog_run(results, output_dir=output_dir, run_date=run_date)
            if _verify_output(Path(output_dir) / "blog.md", "PHASE 1"):
                return True
        except Exception as e:
            logger.error(f"[PHASE 1] Attempt {attempt} failed: {e}")
    return False


def run_phase2(output_dir: str, max_retries: int = 2) -> bool:
    """PHASE 2 순차: Reviewer (Sonnet) → output/blog_reviewed.md"""
    _print_phase(2, "Reviewer (Sonnet) — 품질 검수·개선", "순차")
    from agents.reviewer import run as reviewer_run

    for attempt in range(1, max_retries + 1):
        try:
            reviewer_run(output_dir=output_dir)
            if _verify_output(Path(output_dir) / "blog_reviewed.md", "PHASE 2"):
                return True
        except Exception as e:
            logger.error(f"[PHASE 2] Attempt {attempt} failed: {e}")
    return False


def _run_single_phase3_agent(agent_name: str, output_dir: str) -> tuple[str, bool]:
    try:
        if agent_name == "newsletter":
            from agents.newsletter_writer import run
        elif agent_name == "threads":
            from agents.threads_writer import run
        elif agent_name == "instagram":
            from agents.instagram_writer import run
        else:
            return agent_name, False
        run(output_dir=output_dir)
        out_file = Path(output_dir) / f"{agent_name}.md"
        ok = _verify_output(out_file, f"PHASE 3/{agent_name}")
        return agent_name, ok
    except Exception as e:
        logger.error(f"[PHASE 3/{agent_name}] Error: {e}")
        return agent_name, False


def run_phase3(output_dir: str) -> dict[str, bool]:
    """PHASE 3 병렬: Newsletter / Threads / Instagram (Sonnet×3)"""
    _print_phase(3, "Newsletter · Threads · Instagram (Sonnet×3)", "병렬 동시 실행")
    agents = ["newsletter", "threads", "instagram"]
    results_map: dict[str, bool] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_run_single_phase3_agent, a, output_dir): a for a in agents}
        for future in concurrent.futures.as_completed(futures):
            agent_name, ok = future.result()
            results_map[agent_name] = ok
            status = "✅" if ok else "❌"
            logger.info(f"[PHASE 3] {status} {agent_name}")

    return results_map


def run_phase4(output_dir: str, run_date: str) -> dict:
    """PHASE 4 최종: Notion Uploader (Sonnet+MCP)"""
    _print_phase(4, "Notion Uploader (Sonnet + MCP: notion-create-pages)", "최종")
    from agents.notion_uploader import run as notion_run
    return notion_run(output_dir=output_dir, run_date=run_date)


def main(
    tickers: Optional[List[str]] = None,
    days: int = 20,
    top_n: int = 5,
    output_dir: str = "output",
    z_threshold: float = 2.0,
    lookforward_days: int = 20,
    skip_notion: bool = False,
) -> None:
    print("=" * 60)
    print("  콘텐츠 멀티에이전트 시스템 — 외국인 순매수 셜록홈즈")
    print("=" * 60)
    print("  에이전트는 인자가 아니라 output/ 공유 파일을 읽고 씀")
    print("  Orchestrator: CLAUDE.md + agents/orchestrator.md")
    print("  단계 실행 · 산출물 검증 · 실패 시 재시도 · 진행 보고")

    tickers = tickers or DEFAULT_UNIVERSE
    run_date = datetime.today().strftime("%Y년 %m월 %d일")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # ── 데이터 수집 + 추리 (기존 파이프라인) ─────────────────────
    print(f"\n{'─'*60}")
    print(f"  [사전] 수집 에이전트 + 추리 에이전트 실행")
    print(f"{'─'*60}")
    logger.info(f"Universe: {len(tickers)}개 종목 / {days}일 / top-{top_n}")

    from agents.collector import collect_universe
    from agents.detective import screen_universe

    universe_data = collect_universe(tickers, days=days)
    results = screen_universe(
        universe_data,
        z_threshold=z_threshold,
        lookforward_days=lookforward_days,
        top_n=top_n,
    )

    # Save analysis JSON
    json_path = Path(output_dir) / "results.json"
    serializable = [{k: v for k, v in r.items() if not hasattr(v, "to_dict")} for r in results]
    json_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"분석 결과 저장: {json_path}")

    # ── PHASE 1 ──────────────────────────────────────────────────
    ok1 = run_phase1(results, output_dir=output_dir, run_date=run_date)
    if not ok1:
        logger.error("PHASE 1 실패 — 파이프라인 중단")
        sys.exit(1)

    # ── PHASE 2 ──────────────────────────────────────────────────
    ok2 = run_phase2(output_dir=output_dir)
    if not ok2:
        logger.error("PHASE 2 실패 — 파이프라인 중단")
        sys.exit(1)

    # ── PHASE 3 (병렬) ───────────────────────────────────────────
    phase3_results = run_phase3(output_dir=output_dir)
    if not any(phase3_results.values()):
        logger.error("PHASE 3 전체 실패 — 파이프라인 중단")
        sys.exit(1)

    # ── PHASE 4 ──────────────────────────────────────────────────
    notion_results = {}
    if not skip_notion:
        notion_results = run_phase4(output_dir=output_dir, run_date=run_date)

    # ── 최종 요약 ────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  📊 파이프라인 완료 — 최종 요약")
    print(f"{'='*60}")
    print(f"  PHASE 1 Blog Writer  : {'✅' if ok1 else '❌'}")
    print(f"  PHASE 2 Reviewer     : {'✅' if ok2 else '❌'}")
    for agent, ok in phase3_results.items():
        print(f"  PHASE 3 {agent:<12}: {'✅' if ok else '❌'}")
    print(f"  PHASE 4 Notion       : {'✅' if notion_results else '⏭️ 건너뜀 (--skip-notion)'}")
    print()
    print("  output/ 산출물:")
    for f in sorted(Path(output_dir).glob("*.md")):
        print(f"    {f.name} ({f.stat().st_size:,} bytes)")
    if notion_results:
        print("\n  Notion 페이지:")
        for key, url in notion_results.items():
            print(f"    {key}: {url}")
    print()

    print("  추리 결과 상위 종목:")
    for r in results:
        print(f"    [{r['ticker']}] 확신도 {r['conviction_pct']}% — {r['hypothesis'][:45]}...")
    print()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="외국인 순매수 셜록홈즈 콘텐츠 멀티에이전트")
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--days", type=int, default=20)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--z-threshold", type=float, default=2.0)
    parser.add_argument("--lookforward", type=int, default=20)
    parser.add_argument("--skip-notion", action="store_true", help="Notion 업로드 건너뜀")
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
        skip_notion=args.skip_notion,
    )
