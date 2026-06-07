"""
collector.py - Data Collection Agent for 외국인 순매수 셜록홈즈

Fetches foreign net-buy, OHLCV, short-selling, and DART disclosure data.

NOTE on KRX vs NXT split:
  2025년부터 KRX(한국거래소)와 NXT(넥스트레이드)로 시장이 분리됨.
  pykrx는 현재 KRX 데이터만 커버할 가능성이 높으며,
  NXT를 통한 외국인 순매수가 집계에서 누락될 수 있음.
  향후 pykrx 업데이트 또는 NXT 별도 API 연동 필요.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _date_str(d: datetime) -> str:
    return d.strftime("%Y%m%d")


def fetch_foreign_net_buy(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetch foreign net-buy value by date for a single ticker.

    Uses pykrx stock.get_market_trading_value_by_date().
    Returns DataFrame with columns: [외국인합계] (net buy KRW).

    Source tier: [1차] KRX 공식 외국인 거래 데이터
    """
    try:
        from pykrx import stock

        df = stock.get_market_trading_value_by_date(start_date, end_date, ticker)
        if df is None or df.empty:
            logger.warning(f"[{ticker}] No foreign trading data for {start_date}~{end_date}")
            return pd.DataFrame()

        # pykrx returns columns like: 기관합계, 기타법인, 개인, 외국인합계, 전체
        if "외국인합계" in df.columns:
            result = df[["외국인합계"]].copy()
        else:
            # Fallback: try to identify foreign column
            foreign_cols = [c for c in df.columns if "외국인" in c]
            if not foreign_cols:
                logger.warning(f"[{ticker}] Cannot find foreign column in: {df.columns.tolist()}")
                return pd.DataFrame()
            result = df[[foreign_cols[0]]].rename(columns={foreign_cols[0]: "외국인합계"})

        result.index.name = "date"
        result.attrs["source"] = "[1차] KRX 공식 외국인 거래 데이터 (pykrx)"
        result.attrs["as_of_date"] = end_date
        result.attrs["ticker"] = ticker
        return result

    except Exception as e:
        logger.error(f"[{ticker}] fetch_foreign_net_buy error: {e}")
        return pd.DataFrame()


def fetch_ohlcv(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetch OHLCV (Open/High/Low/Close/Volume) data for a ticker.

    Uses pykrx stock.get_market_ohlcv_by_date().
    Returns DataFrame with columns: [시가, 고가, 저가, 종가, 거래량].

    Source tier: [2차] pykrx OHLCV
    """
    try:
        from pykrx import stock

        df = stock.get_market_ohlcv_by_date(start_date, end_date, ticker)
        if df is None or df.empty:
            logger.warning(f"[{ticker}] No OHLCV data for {start_date}~{end_date}")
            return pd.DataFrame()

        df.index.name = "date"
        df.attrs["source"] = "[2차] pykrx OHLCV"
        df.attrs["as_of_date"] = end_date
        df.attrs["ticker"] = ticker
        return df

    except Exception as e:
        logger.error(f"[{ticker}] fetch_ohlcv error: {e}")
        return pd.DataFrame()


def fetch_foreign_holding_rate(ticker: str) -> Optional[float]:
    """
    Fetch current foreign holding rate (%) for a ticker.

    Uses pykrx stock.get_market_cap_by_date() or similar.
    Returns float percentage (e.g., 52.3 means 52.3%).

    Note: pykrx doesn't have a direct "foreign holding rate" API.
    We approximate using the latest available date's data.

    Source tier: [2차] pykrx 외국인 보유율 추정
    """
    try:
        from pykrx import stock

        end_date = datetime.today()
        start_date = end_date - timedelta(days=5)
        start_str = _date_str(start_date)
        end_str = _date_str(end_date)

        # get_exhaustion_rates_of_foreign_investment_by_date gives foreign holding info
        try:
            df = stock.get_exhaustion_rates_of_foreign_investment_by_date(
                start_str, end_str, ticker
            )
        except Exception:
            return None

        if df is None or df.empty:
            return None

        # Columns typically: 상장주식수, 보유수량, 지분율, 한도수량, 한도소진률
        if "지분율" in df.columns:
            latest_rate = df["지분율"].dropna().iloc[-1] if not df["지분율"].dropna().empty else None
            return float(latest_rate) if latest_rate is not None else None

        return None

    except Exception as e:
        logger.error(f"[{ticker}] fetch_foreign_holding_rate error: {e}")
        return None


def fetch_short_selling(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Fetch short-selling data for a ticker.

    Uses pykrx stock.get_market_short_sell_by_date().
    Returns DataFrame with short-sell volume and value.

    Source tier: [2차] pykrx 공매도 데이터
    """
    try:
        from pykrx import stock

        df = stock.get_shorting_volume_by_date(start_date, end_date, ticker)
        if df is None or df.empty:
            logger.warning(f"[{ticker}] No short-sell data for {start_date}~{end_date}")
            return pd.DataFrame()

        # Normalize column: pykrx may return '거래량' or '공매도' depending on version
        vol_candidates = [c for c in df.columns if "거래량" in c or "공매도" in c or "volume" in c.lower()]
        if not vol_candidates:
            logger.warning(f"[{ticker}] Unexpected shorting columns: {df.columns.tolist()}")
            return pd.DataFrame()

        df.index.name = "date"
        df.attrs["source"] = "[2차] pykrx 공매도 데이터"
        df.attrs["as_of_date"] = end_date
        df.attrs["ticker"] = ticker
        return df

    except Exception as e:
        logger.warning(f"[{ticker}] fetch_short_selling unavailable: {e}")
        return pd.DataFrame()


def fetch_dart_disclosures(
    ticker: str,
    start_date: str,
    end_date: str,
    corp_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch DART disclosures for a ticker (using dart_fss / OpenDartReader).

    Looks for:
    - 5% 대량보유 보고서 (large holding reports)
    - 주요사항보고서 (material events)
    - 사업보고서 (business reports)

    Returns list of disclosure dicts with keys: rcept_dt, report_nm, corp_name, etc.

    Source tier: [1차] DART 공시 (금융감독원 전자공시)
    """
    import os

    dart_key = os.environ.get("DART_API_KEY", "")
    if not dart_key:
        logger.warning("DART_API_KEY not set, skipping DART disclosures")
        return []

    try:
        import dart_fss as dart

        dart.set_api_key(dart_key)

        # Convert ticker to corp_code if not provided
        if corp_code is None:
            try:
                corp_list = dart.get_corp_list()
                # corp_list has stock_code attribute
                matched = [c for c in corp_list.corps if hasattr(c, "stock_code") and c.stock_code == ticker]
                if not matched:
                    logger.warning(f"[{ticker}] Cannot find corp_code in DART")
                    return []
                corp_code = matched[0].corp_code
            except Exception as e:
                logger.error(f"[{ticker}] DART corp lookup error: {e}")
                return []

        # Fetch disclosures
        # dart_fss uses bgn_de/end_de format YYYYMMDD
        try:
            filings = dart.filings.search(
                corp_code=corp_code,
                bgn_de=start_date,
                end_de=end_date,
                pblntf_ty="A",  # All types
            )
        except Exception:
            # Fallback: try without pblntf_ty
            try:
                filings = dart.filings.search(
                    corp_code=corp_code,
                    bgn_de=start_date,
                    end_de=end_date,
                )
            except Exception as e2:
                logger.error(f"[{ticker}] DART search error: {e2}")
                return []

        results = []
        if filings and hasattr(filings, "list"):
            for f in filings.list:
                results.append(
                    {
                        "rcept_dt": getattr(f, "rcept_dt", ""),
                        "report_nm": getattr(f, "report_nm", ""),
                        "corp_name": getattr(f, "corp_name", ""),
                        "rcept_no": getattr(f, "rcept_no", ""),
                        "source": "[1차] DART 공시",
                        "as_of_date": end_date,
                    }
                )

        return results

    except Exception as e:
        logger.error(f"[{ticker}] fetch_dart_disclosures error: {e}")
        return []


def collect_universe(
    tickers: List[str],
    days: int = 20,
) -> Dict[str, Dict[str, Any]]:
    """
    Collect all data for a list of tickers over the past `days` days.

    Returns:
        {
          ticker: {
            "foreign_net_buy": DataFrame,   # daily foreign net buy KRW
            "ohlcv": DataFrame,             # daily OHLCV
            "foreign_holding_rate": float,  # current % holding
            "short_selling": DataFrame,     # daily short sell data
            "dart_disclosures": List[dict], # DART filings
            "meta": {
                "ticker": str,
                "days": int,
                "start_date": str,
                "end_date": str,
                "collected_at": str,
            }
          }
        }

    Each DataFrame has .attrs["source"] and .attrs["as_of_date"] set.

    NOTE: KRX vs NXT split (2025~)
      pykrx currently covers KRX only. NXT(넥스트레이드) volume not included.
      Foreign net-buy figures may be understated for stocks with significant NXT activity.
    """
    end_dt = datetime.today()
    start_dt = end_dt - timedelta(days=days + 10)  # buffer for holidays
    start_str = _date_str(start_dt)
    end_str = _date_str(end_dt)

    # Wider window for DART (look back further for context)
    dart_start_dt = end_dt - timedelta(days=days + 30)
    dart_start_str = _date_str(dart_start_dt)

    universe_data: Dict[str, Dict[str, Any]] = {}

    for ticker in tickers:
        logger.info(f"Collecting data for {ticker}...")
        try:
            foreign_net_buy = fetch_foreign_net_buy(ticker, start_str, end_str)
            ohlcv = fetch_ohlcv(ticker, start_str, end_str)
            holding_rate = fetch_foreign_holding_rate(ticker)
            short_selling = fetch_short_selling(ticker, start_str, end_str)
            dart_disclosures = fetch_dart_disclosures(ticker, dart_start_str, end_str)

            universe_data[ticker] = {
                "foreign_net_buy": foreign_net_buy,
                "ohlcv": ohlcv,
                "foreign_holding_rate": holding_rate,
                "short_selling": short_selling,
                "dart_disclosures": dart_disclosures,
                "meta": {
                    "ticker": ticker,
                    "days": days,
                    "start_date": start_str,
                    "end_date": end_str,
                    "collected_at": datetime.now().isoformat(),
                    # Source tagging
                    "foreign_net_buy_source": "[1차] KRX 공식 외국인 거래 데이터 (pykrx)",
                    "ohlcv_source": "[2차] pykrx OHLCV",
                    "holding_rate_source": "[2차] pykrx 외국인 보유율 추정",
                    "short_selling_source": "[2차] pykrx 공매도 데이터",
                    "dart_source": "[1차] DART 공시 (금융감독원 전자공시)",
                    # NXT warning
                    "nxt_warning": (
                        "2025년부터 NXT(넥스트레이드) 분리로 외국인 순매수 집계가 "
                        "KRX 분만 포함될 수 있음. NXT 거래량 누락 가능성 있음."
                    ),
                },
            }
        except Exception as e:
            logger.error(f"[{ticker}] collect_universe error: {e}")
            universe_data[ticker] = {
                "foreign_net_buy": pd.DataFrame(),
                "ohlcv": pd.DataFrame(),
                "foreign_holding_rate": None,
                "short_selling": pd.DataFrame(),
                "dart_disclosures": [],
                "meta": {
                    "ticker": ticker,
                    "days": days,
                    "start_date": start_str,
                    "end_date": end_str,
                    "collected_at": datetime.now().isoformat(),
                    "error": str(e),
                },
            }

    logger.info(f"Collection complete. {len(universe_data)} tickers processed.")
    return universe_data
