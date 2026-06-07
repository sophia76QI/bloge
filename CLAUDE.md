# 외국인 순매수 셜록홈즈 (Foreign Net-Buy Sherlock Holmes)

## Project Overview

A multi-agent Python system that detects abnormal foreign net-buy patterns in KOSPI stocks, generates hypotheses about the underlying causes, and publishes findings as Korean blog posts.

## Architecture

```
orchestrator.py
├── agents/collector.py   - Data collection (pykrx, dart_fss)
├── agents/detective.py   - Statistical lead-lag detection
└── agents/publisher.py   - Korean blog/threads output
```

## System Prompt (Orchestrator)

당신은 한국 주식시장의 외국인 순매수 패턴을 분석하는 셜록 홈즈입니다.
- 데이터를 수집하고, 이상 패턴을 탐지하고, 가설을 세우고, 증거를 검증합니다.
- 모든 분석은 확증 편향을 피하고, 반증 가능성을 항상 열어둡니다.
- 출처 신뢰도를 명시하고 (1차/2차/3차/추측), 시간 지평을 태깅합니다.
- 최종 결론은 유죄/무죄가 아닌 "가능성 %" 형태로 표현합니다.

## Data Sources & Tiers

- [1차] KRX 공식 외국인 순매수 데이터 (pykrx)
- [1차] DART 공시 (dart_fss / OpenDartReader)
- [2차] pykrx OHLCV, 시가총액, 공매도
- [3차] 파생 통계 (Z-score, 리드-래그 분석)
- [추측] 외부 정보 없이 패턴만으로 추론

## NXT Split Note (2025)

2025년부터 KRX와 NXT(넥스트레이드)로 시장이 분리됨.
pykrx는 현재 KRX 데이터만 커버할 가능성이 높음.
외국인 순매수 집계 시 NXT 분 누락 가능성 있음 - 해석 시 주의 필요.

## Output Format

- `output/` 디렉토리에 타임스탬프 파일명으로 저장
- `blog_YYYYMMDD_HHMMSS.md` - 한국어 블로그 포스트
- `threads_YYYYMMDD_HHMMSS.txt` - 쓰레드용 짧은 포스트
- `analysis_YYYYMMDD_HHMMSS.json` - 원본 분석 데이터

## Disclaimer

본 분석은 교육 목적의 통계적 패턴 탐지이며 투자 조언이 아닙니다.
외국인 순매수는 다양한 이유(인덱스 리밸런싱, 환헤지, 차익거래 등)로 발생할 수 있으며,
과거 패턴이 미래 수익을 보장하지 않습니다.
투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run with default universe (30 KOSPI blue-chips)
python orchestrator.py

# Run with specific tickers
python orchestrator.py --tickers 005930 000660 035420

# Custom options
python orchestrator.py --days 30 --top-n 5 --output-dir ./my_output
```
