"""
detective.py - Lead-Lag Detection Agent for 외국인 순매수 셜록홈즈

Applies statistical screening to identify tickers where foreign buying
appears to have preceded positive price events or DART disclosures.
All conclusions are expressed as probability-weighted hypotheses — never
as definitive judgements about intent or legality.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Keywords that suggest a positive (bullish) DART disclosure
POSITIVE_KEYWORDS = [
    "계약", "수주", "투자", "인수", "합병", "흑자", "증가", "상향",
    "배당", "자사주", "목표가", "호재", "성장", "실적", "서프라이즈",
    "신규", "협약", "파트너", "공급", "선정",
]

# Keywords that suggest noise (passive / technical flows)
NOISE_KEYWORDS = [
    "편입", "리밸런싱", "만기", "배당락", "자사주소각", "주식병합",
]


def compute_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    """
    Compute rolling Z-score of a series.

    Z = (x - rolling_mean) / rolling_std
    Uses min_periods=max(10, window//3) to allow partial windows.

    Source tier: [추측] 통계적 파생 지표
    """
    rolling_mean = series.rolling(window=window, min_periods=max(10, window // 3)).mean()
    rolling_std = series.rolling(window=window, min_periods=max(10, window // 3)).std()
    zscore = (series - rolling_mean) / rolling_std.replace(0, np.nan)
    return zscore


def detect_abnormal_buy(
    df_foreign: pd.DataFrame,
    z_threshold: float = 2.0,
    col: str = "외국인합계",
) -> List[str]:
    """
    Identify dates where foreign net-buy Z-score exceeds threshold.

    Returns list of date strings (YYYYMMDD) that qualify as t0 candidates.

    Source tier: [추측] Z-score 통계 기반 이상 탐지
    """
    if df_foreign is None or df_foreign.empty or col not in df_foreign.columns:
        return []

    series = df_foreign[col].fillna(0)
    if len(series) < 5:
        return []

    zscores = compute_zscore(series)
    abnormal_dates = zscores[zscores > z_threshold].index

    return [d.strftime("%Y%m%d") if hasattr(d, "strftime") else str(d) for d in abnormal_dates]


def check_lead_lag(
    ticker_data: Dict[str, Any],
    t0_dates: List[str],
    lookforward_days: int = 20,
    price_surge_threshold: float = 0.05,
) -> List[Dict[str, Any]]:
    """
    For each t0 date, check if a positive price or DART event followed within lookforward_days.

    Returns list of lead-lag evidence dicts:
      {
        "t0": str,
        "event_date": str,
        "event_type": str,   # "price_surge" | "dart_positive"
        "event_detail": str,
        "days_lag": int,
        "source": str,
      }

    Source tier: [1차/2차] pykrx OHLCV / DART 공시
    """
    ohlcv = ticker_data.get("ohlcv", pd.DataFrame())
    dart_disclosures = ticker_data.get("dart_disclosures", [])
    evidence_list = []

    if ohlcv.empty or "종가" not in ohlcv.columns:
        return evidence_list

    for t0_str in t0_dates:
        try:
            t0 = pd.Timestamp(t0_str)
        except Exception:
            continue

        t_end = t0 + timedelta(days=lookforward_days)

        # --- Price surge check ---
        future_ohlcv = ohlcv[(ohlcv.index > t0) & (ohlcv.index <= t_end)]
        if not future_ohlcv.empty:
            t0_close_candidates = ohlcv[ohlcv.index <= t0]["종가"]
            if not t0_close_candidates.empty:
                t0_close = t0_close_candidates.iloc[-1]
                max_future_close = future_ohlcv["종가"].max()
                if t0_close > 0:
                    return_pct = (max_future_close - t0_close) / t0_close
                    if return_pct >= price_surge_threshold:
                        peak_date = future_ohlcv["종가"].idxmax()
                        days_lag = (peak_date - t0).days
                        evidence_list.append(
                            {
                                "t0": t0_str,
                                "event_date": peak_date.strftime("%Y%m%d"),
                                "event_type": "price_surge",
                                "event_detail": f"주가 {return_pct*100:.1f}% 상승 (t0 종가 기준)",
                                "days_lag": days_lag,
                                "source": "[2차] pykrx OHLCV",
                            }
                        )

        # --- DART positive disclosure check ---
        for disc in dart_disclosures:
            disc_date_str = disc.get("rcept_dt", "")
            if not disc_date_str:
                continue
            try:
                disc_date = pd.Timestamp(disc_date_str)
            except Exception:
                continue
            if t0 < disc_date <= t_end:
                report_nm = disc.get("report_nm", "")
                is_positive = any(kw in report_nm for kw in POSITIVE_KEYWORDS)
                if is_positive:
                    days_lag = (disc_date - t0).days
                    evidence_list.append(
                        {
                            "t0": t0_str,
                            "event_date": disc_date_str,
                            "event_type": "dart_positive",
                            "event_detail": f"DART 호재성 공시: {report_nm}",
                            "days_lag": days_lag,
                            "source": "[1차] DART 공시",
                        }
                    )

    return evidence_list


def filter_noise(ticker_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess noise factors that could explain foreign buying without information advantage.

    Returns dict:
      {
        "short_sell_spike": bool,
        "passive_suspected": bool,
        "noise_score": float,   # 0.0 = clean, 1.0 = very noisy
        "noise_reasons": List[str],
      }

    Source tier: [2차] pykrx 공매도 데이터
    """
    noise_reasons: List[str] = []
    noise_score = 0.0

    short_sell_df = ticker_data.get("short_selling", pd.DataFrame())
    ohlcv = ticker_data.get("ohlcv", pd.DataFrame())
    dart_disclosures = ticker_data.get("dart_disclosures", [])

    # Check short-selling spike (possible hedge/arb)
    short_sell_spike = False
    if not short_sell_df.empty:
        vol_col = [c for c in short_sell_df.columns if "거래량" in c or "공매도" in c]
        if vol_col:
            ss_series = short_sell_df[vol_col[0]].fillna(0)
            if len(ss_series) >= 5:
                ss_zscore = compute_zscore(ss_series)
                if (ss_zscore > 2.0).any():
                    short_sell_spike = True
                    noise_score += 0.4
                    noise_reasons.append("공매도 급증 — 헷지/차익 가능성 [2차]")

    # Check DART for passive/rebalancing keywords
    passive_suspected = False
    for disc in dart_disclosures:
        report_nm = disc.get("report_nm", "")
        if any(kw in report_nm for kw in NOISE_KEYWORDS):
            passive_suspected = True
            noise_score += 0.3
            noise_reasons.append(f"인덱스 편입/리밸런싱 공시 감지: {report_nm} [1차]")
            break

    # High volume on many consecutive days (passive fund inflow pattern)
    if not ohlcv.empty and "거래량" in ohlcv.columns:
        vol = ohlcv["거래량"].fillna(0)
        if len(vol) >= 5:
            vol_zscore = compute_zscore(vol)
            consecutive_high = (vol_zscore > 1.5).rolling(3).sum()
            if (consecutive_high >= 3).any():
                noise_score += 0.1
                noise_reasons.append("연속 대량 거래 감지 — 패시브 유입 가능성 [추측]")

    noise_score = min(noise_score, 1.0)

    return {
        "short_sell_spike": short_sell_spike,
        "passive_suspected": passive_suspected,
        "noise_score": noise_score,
        "noise_reasons": noise_reasons,
    }


def cross_check(ticker_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cross-check DART 5% large holding reports for quiet accumulation evidence.

    Returns dict:
      {
        "large_holding_reports": List[str],  # report names
        "accumulation_signal": bool,
      }

    Source tier: [1차] DART 5% 대량보유보고
    """
    dart_disclosures = ticker_data.get("dart_disclosures", [])
    large_holding_keywords = ["대량보유", "5%", "주요주주", "임원", "소유변동"]

    large_holding_reports = []
    for disc in dart_disclosures:
        report_nm = disc.get("report_nm", "")
        if any(kw in report_nm for kw in large_holding_keywords):
            large_holding_reports.append(f"{disc.get('rcept_dt','')} {report_nm}")

    return {
        "large_holding_reports": large_holding_reports,
        "accumulation_signal": len(large_holding_reports) > 0,
    }


def score_hypothesis(
    ticker: str,
    ticker_data: Dict[str, Any],
    z_threshold: float = 2.0,
    lookforward_days: int = 20,
) -> Dict[str, Any]:
    """
    Compute a conviction score (0-100%) for the "information-advantage" hypothesis.

    Scoring model:
      Base:   lead-lag evidence × 30pts each (capped at 60)
      Boost:  accumulation signal +15pts
              short lag (<7 days) +10pts bonus per event
      Penalty: noise_score × 30pts deducted

    Returns:
      {
        "ticker": str,
        "conviction_pct": int,          # 0–100
        "hypothesis": str,              # one-line Korean hypothesis
        "evidence": List[str],          # with source tiers
        "counter_scenarios": List[str], # falsification scenarios
        "t0_dates": List[str],
        "lead_lag_events": List[dict],
        "noise_assessment": dict,
        "cross_check": dict,
        "as_of_date": str,
      }
    """
    as_of = ticker_data.get("meta", {}).get("end_date", datetime.today().strftime("%Y%m%d"))

    t0_dates = detect_abnormal_buy(
        ticker_data.get("foreign_net_buy", pd.DataFrame()),
        z_threshold=z_threshold,
    )

    lead_lag_events = check_lead_lag(ticker_data, t0_dates, lookforward_days=lookforward_days)
    noise = filter_noise(ticker_data)
    cc = cross_check(ticker_data)

    # --- Scoring ---
    base_score = min(len(lead_lag_events) * 30, 60)

    bonus = 0
    if cc["accumulation_signal"]:
        bonus += 15
    for evt in lead_lag_events:
        if evt.get("days_lag", 99) < 7:
            bonus += 10
            break  # one-time bonus

    penalty = int(noise["noise_score"] * 30)
    conviction_pct = max(0, min(100, base_score + bonus - penalty))

    # --- Evidence list ---
    evidence: List[str] = []
    if t0_dates:
        evidence.append(
            f"이상 매수 탐지일(t0): {', '.join(t0_dates[:3])} — Z-score>{z_threshold} [추측]"
        )
    for evt in lead_lag_events:
        evidence.append(
            f"선행성 확인: {evt['event_detail']} (t0+{evt['days_lag']}일) {evt['source']}"
        )
    if cc["accumulation_signal"]:
        for rpt in cc["large_holding_reports"]:
            evidence.append(f"대량보유 공시: {rpt} [1차]")
    if noise["noise_reasons"]:
        for r in noise["noise_reasons"]:
            evidence.append(f"노이즈 요인: {r}")

    # --- Counter-scenarios ---
    counter_scenarios = [
        "단순 패시브 펀드(ETF) 리밸런싱으로 인한 기계적 매수일 수 있음 [추측]",
        "공매도 포지션 커버(숏 스퀴즈)로 인한 외국인 순매수 착시 가능성 [추측]",
        "배당락·자사주 매입 일정에 따른 기술적 매수일 수 있음 [추측]",
    ]
    if not lead_lag_events:
        counter_scenarios.insert(0, "선행성 이벤트가 관찰 기간 내 미발생 — 가설 근거 약함 [추측]")

    # --- One-line hypothesis ---
    if conviction_pct >= 60:
        strength = "강한"
    elif conviction_pct >= 35:
        strength = "중간 수준의"
    else:
        strength = "약한"
    hypothesis = (
        f"외국인의 정보 우위로 보이는 선행 매수 패턴 관찰 "
        f"— {strength} 확신도로 {conviction_pct}% 가설"
    )

    return {
        "ticker": ticker,
        "conviction_pct": conviction_pct,
        "hypothesis": hypothesis,
        "evidence": evidence,
        "counter_scenarios": counter_scenarios,
        "t0_dates": t0_dates,
        "lead_lag_events": lead_lag_events,
        "noise_assessment": noise,
        "cross_check": cc,
        "as_of_date": as_of,
    }


def screen_universe(
    universe_data: Dict[str, Dict[str, Any]],
    z_threshold: float = 2.0,
    lookforward_days: int = 20,
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """
    Screen all tickers and return top N by conviction_pct descending.

    Source tier: [추측] 통계 스크리닝
    """
    results = []
    for ticker, ticker_data in universe_data.items():
        try:
            result = score_hypothesis(
                ticker, ticker_data,
                z_threshold=z_threshold,
                lookforward_days=lookforward_days,
            )
            results.append(result)
        except Exception as e:
            logger.error(f"[{ticker}] score_hypothesis error: {e}")

    results.sort(key=lambda r: r.get("conviction_pct", 0), reverse=True)
    return results[:top_n]
