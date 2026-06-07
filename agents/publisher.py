"""
publisher.py - Output Agent for 외국인 순매수 셜록홈즈

Converts detective results into Korean-language content:
  - Blog post (startup-diary / stock-detective tone)
  - Threads post (4044 formula)

All outputs include the mandatory disclaimer at the bottom.
Tone: 친근+전문, 단정 금지 ("무조건"·"100%" 사용 안 함).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

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


def _time_horizon_tag(conviction_pct: int) -> str:
    if conviction_pct >= 60:
        return "[중기 트렌드]"
    elif conviction_pct >= 35:
        return "[단기 노이즈 주의]"
    else:
        return "[단기 노이즈]"


def format_blog_post(
    results: List[Dict[str, Any]],
    run_date: str | None = None,
) -> str:
    """
    Generate a Korean blog post following the 4-PHASE Sherlock structure.

    PHASE 1 (수집) → PHASE 2 (가설) → PHASE 3 (검증) → PHASE 4 (결론)

    Source tiers [1차/2차/3차/추측] are embedded in evidence lines.
    Time horizon tags [단기 노이즈][중기 트렌드][구조적 변화] label each section.
    Counter-scenarios ("이 가설이 틀렸다면?") included per ticker.
    """
    today = run_date or datetime.today().strftime("%Y년 %m월 %d일")
    lines: List[str] = []

    lines.append(f"# 🔍 외국인 순매수 셜록홈즈 — {today} 추리 리포트")
    lines.append("")
    lines.append(
        "> 공개 데이터(KRX·DART)로 외국인 선행 매수 패턴을 추리합니다. "
        "이 리포트의 모든 결론은 '확신도 %를 붙인 가설'이며, "
        "특정 기업·기관의 위법 행위를 단정하지 않습니다."
    )
    lines.append("")

    # ── PHASE 1: 수집 ──────────────────────────────────────────
    lines.append("---")
    lines.append("## PHASE 1 · 수집 — 오늘의 스크리닝 유니버스")
    lines.append("")
    lines.append(f"- 분석 종목 수: **{len(results)}개** (스크리닝 후 상위 종목)")
    lines.append("- 데이터 출처: KRX 외국인 거래실적 [1차], DART 전자공시 [1차], pykrx OHLCV [2차]")
    lines.append(
        "- ⚠️ NXT 주의: 2025년 넥스트레이드(NXT) 도입으로 KRX 외 거래량은 "
        "현재 집계에서 누락될 수 있습니다. pykrx = KRX 단독 기준."
    )
    lines.append("")

    # ── PHASE 2: 가설 ──────────────────────────────────────────
    lines.append("---")
    lines.append("## PHASE 2 · 가설 — 이상 매수 탐지 결과")
    lines.append("")
    lines.append(
        "Z-score 기반 이상 매수 탐지 후, 선행성(lead-lag) 검증을 통과한 종목입니다. "
        "[추측] 통계적 파생 지표"
    )
    lines.append("")

    for i, r in enumerate(results, 1):
        ticker = r.get("ticker", "???")
        conviction = r.get("conviction_pct", 0)
        hypothesis = r.get("hypothesis", "")
        tag = _time_horizon_tag(conviction)
        t0_dates = r.get("t0_dates", [])

        lines.append(f"### {i}. 종목 {ticker} {tag}")
        lines.append(f"**{hypothesis}**")
        lines.append("")
        if t0_dates:
            lines.append(f"- 이상 매수 탐지일(t0): {', '.join(t0_dates[:3])}")
        lines.append("")

    # ── PHASE 3: 검증 ──────────────────────────────────────────
    lines.append("---")
    lines.append("## PHASE 3 · 검증 — 선행성·노이즈·교차확인")
    lines.append("")

    for r in results:
        ticker = r.get("ticker", "???")
        conviction = r.get("conviction_pct", 0)
        evidence = r.get("evidence", [])
        noise = r.get("noise_assessment", {})
        cc = r.get("cross_check", {})

        lines.append(f"### 종목 {ticker} — 확신도 {conviction}%")
        lines.append("")

        if evidence:
            lines.append("**📌 근거 수치 (출처 위계 포함)**")
            for ev in evidence:
                lines.append(f"- {ev}")
            lines.append("")

        if noise.get("noise_reasons"):
            lines.append("**🔇 노이즈 제거 검토**")
            for nr in noise["noise_reasons"]:
                lines.append(f"- {nr}")
            lines.append(f"- 노이즈 점수: {noise.get('noise_score', 0):.1f} / 1.0 [추측]")
            lines.append("")

        if cc.get("accumulation_signal"):
            lines.append("**📋 대량보유 공시 교차확인 [1차]**")
            for rpt in cc.get("large_holding_reports", []):
                lines.append(f"- {rpt}")
            lines.append("")

    # ── PHASE 4: 결론 ──────────────────────────────────────────
    lines.append("---")
    lines.append("## PHASE 4 · 결론 — 확신도 가설 + 반증")
    lines.append("")

    for r in results:
        ticker = r.get("ticker", "???")
        conviction = r.get("conviction_pct", 0)
        hypothesis = r.get("hypothesis", "")
        counter = r.get("counter_scenarios", [])
        as_of = r.get("as_of_date", "")
        tag = _time_horizon_tag(conviction)

        lines.append(f"### 종목 {ticker} {tag}")
        lines.append(f"> **{hypothesis}**")
        lines.append(f"> 기준일: {as_of} (KRX T-1 종가 기준)")
        lines.append("")

        lines.append("**🔄 이 가설이 틀렸다면?**")
        for cs in counter:
            lines.append(f"- {cs}")
        lines.append("")

        lines.append("**5대 편향 점검**")
        lines.append("- 확증 편향: 매수 이후 하락 케이스도 검토했는가? ✅")
        lines.append("- 사후 확증 편향: t0 날짜는 사후 설정이 아닌 실시간 Z-score 기준 ✅")
        lines.append("- 과적합: 소수 종목에 대한 통계 — 샘플 수 제한 주의 ⚠️")
        lines.append("- 생존 편향: 급락 종목 제외 여부 미확인 ⚠️")
        lines.append("- 귀인 편향: 상관 ≠ 인과 — 외국인 매수가 원인이 아닐 수 있음 ✅")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(DISCLAIMER)

    return "\n".join(lines)


def format_threads_post(
    results: List[Dict[str, Any]],
    run_date: str | None = None,
    max_tickers: int = 3,
) -> str:
    """
    Generate a short Korean Threads post using the 4044 formula:
    4 key points, optimized for ~440 characters per thread chunk.

    Returns a string with thread chunks separated by '---'.
    """
    today = run_date or datetime.today().strftime("%m/%d")
    top = results[:max_tickers]

    threads: List[str] = []

    # Thread 1: Hook
    hook_lines = [f"🔍 [{today}] 외국인이 먼저 움직인 종목이 있습니다.", ""]
    hook_lines.append("공개 데이터로 '스마트머니 흔적'을 추리했습니다.")
    hook_lines.append("(투자 권유 ❌ — 통계 가설입니다)")
    threads.append("\n".join(hook_lines))

    # Thread 2-N: Per ticker
    for r in top:
        ticker = r.get("ticker", "???")
        conviction = r.get("conviction_pct", 0)
        events = r.get("lead_lag_events", [])
        t0_dates = r.get("t0_dates", [])

        body = [f"📌 종목 [{ticker}]"]
        body.append(f"확신도 {conviction}% 가설")
        if t0_dates:
            body.append(f"▸ 이상 매수 탐지: {t0_dates[0]}")
        if events:
            first = events[0]
            body.append(f"▸ {first['event_detail'][:40]} (t0+{first['days_lag']}일)")
        body.append("")
        body.append("이 가설이 틀렸다면?")
        body.append("→ 단순 패시브 유입 or 공매도 커버 가능성")
        threads.append("\n".join(body))

    # Final thread: Disclaimer
    disclaimer_short = (
        "⚠️ 본 콘텐츠는 KRX·DART 공개 데이터 기반 수급 추리입니다.\n"
        "투자 권유 또는 위법 단정이 아니며, 최종 판단은 본인 책임입니다.\n"
        "© 다빈치힐스 · 외국인 순매수 셜록홈즈 v1.0"
    )
    threads.append(disclaimer_short)

    return "\n\n---\n\n".join(threads)
