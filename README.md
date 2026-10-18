# krx-fundamentals-client

[![CI](https://github.com/younghwan91/krx-fundamentals-client/actions/workflows/ci.yml/badge.svg)](https://github.com/younghwan91/krx-fundamentals-client/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/younghwan91/krx-fundamentals-client)](https://github.com/younghwan91/krx-fundamentals-client/blob/main/LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-younghwan--chae-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/younghwan-chae/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.png">
  <img alt="삼성전자 한 종목의 DART 연결 재무제표 8개년(매출·영업이익)과 발행주식수·현재가를 라이브러리로 받아 한 스키마로 그린 그림" src="docs/images/hero-light.png" width="100%">
</picture>

[English](README.en.md)

**DART·KRX·네이버 금융에서 국내 기업 펀더멘탈을 모아 하나의 스키마로 내주는 Python 클라이언트 라이브러리** — 재무제표, 투자지표, 배당, 대주주, 임원, 종목 스크리닝.

[kiwoom-client](https://github.com/younghwan91/kiwoom-client), [krx-news-client](https://github.com/younghwan91/krx-news-client)와 같은 성격의 라이브러리다 — 서버 없이, 호출할 때마다 소스에 직접 요청해 결과를 돌려준다.

> ⛔ **KRX 수집 경로는 현재 막혀 있다 (2026-08 실측).** KRX 로그인 문제로 투자지표·시가총액·섹터가
> 조용히 빈 채로 온다 (상위 100종목은 `NaverScraper`로 대체 가능, DART 경로는 영향 없음).
> 원인 코드 추적은 [docs/krx-blocked.md](docs/krx-blocked.md).

## 설치

```bash
pip install krx-fundamentals-client
```

## 빠른 시작

### 1. DART 기업 정보 및 재무제표 (API 키 무료 발급)

```python
import asyncio
from krx_fundamentals_client import DartScraper

async def main():
    scraper = DartScraper(api_key="...")  # https://opendart.fss.or.kr 무료 발급
    try:
        company = await scraper.fetch_company("005930")
        print(company.name, company.ceo)

        financials = await scraper.fetch_financials("005930", year=2025)
        print(f"매출액: {financials.revenue:,} / 영업이익: {financials.operating_income:,}")
    finally:
        await scraper.close()

asyncio.run(main())
```

### 2. 네이버 금융 투자지표 및 스크리닝 (API 키 불필요)

KRX 공식 수집 경로가 로그인 차단 중인 동안, `NaverScraper`로 PER·PBR·배당수익률·시가총액을 키 없이 즉시 수집하고 스크리닝할 수 있습니다:

```python
import asyncio
from krx_fundamentals_client import NaverScraper, RankingMetric, rank_stocks, screen_stocks

async def main():
    scraper = NaverScraper()
    try:
        # 단일 종목 투자지표
        ratio = await scraper.fetch_stock_info("005930")
        print(f"삼성전자 PER: {ratio.per}, PBR: {ratio.pbr}, 배당수익률: {ratio.dividend_yield}%")

        # 종목군 배치 수집 후 스크리닝 & 랭킹
        ratios = await scraper.fetch_batch(["005930", "000660", "035420", "005380"])
        value_stocks = screen_stocks(ratios, per_max=15.0, pbr_max=1.2)
        top_by_pbr = rank_stocks(ratios, RankingMetric.PBR)
    finally:
        await scraper.close()

asyncio.run(main())
```

배치 조회·키 순환 같은 실전 패턴은 아래 [고급 사용법](#고급-사용법)에, 바로 돌려볼 수 있는
전체 스크립트는 [`examples/`](examples/)에 있다.

## 데이터 소스

| 소스 | 데이터 | 수집 단위 | 인증 |
|-----|-------|----------|------|
| [DART OpenAPI](https://opendart.fss.or.kr) | 기업개황, 재무제표, 배당, 대주주, 임원, 발행주식수 | 종목 단위 (재무제표는 최대 100종목/호출 배치도 가능) | API 키 (무료) |
| [KRX 정보데이터시스템](http://data.krx.co.kr) | PER, PBR, 시가총액, 섹터 | 시장 전체 벌크 CSV | 불필요 (⛔ 현재 로그인 차단) |
| [네이버 금융](https://m.stock.naver.com) | 시세·PER·PBR·EPS·BPS·배당수익률 | 종목 단위 | 불필요 |

## 응답 모델

`Company`, `FinancialStatement`, `InvestmentRatio`, `Dividend`, `Shareholder`, `Executive`, `SharesOutstanding`, `SectorOverview` — 전부 Pydantic 모델이며 `krx_fundamentals_client`에서 바로 import 할 수 있다. 필드는 [`models/schemas.py`](src/krx_fundamentals_client/models/schemas.py) 참고.

## 스크리닝 / 랭킹

`screen_stocks`, `rank_stocks`는 캐시나 상태를 갖지 않는 순수 함수다 — `KrxScraper.fetch_investment_ratios()`로 받은 `list[InvestmentRatio]`를 넘기면 그 자리에서 필터링/정렬해 반환한다.

## 고급 사용법

여러 종목의 재무제표를 한 번에 (DART `fnlttMultiAcnt` 배치, 최대 100종목/호출):

```python
financials = await scraper.fetch_financials_batch(
    ["005930", "000660", "035420"], year=2025,
)
for ticker, fs in financials.items():
    if fs is not None:
        print(ticker, fs.revenue, fs.net_income)
```

DART 키의 일일 한도를 소진하면 `DartScraper`가 `DartQuotaExceededError`를 던진다 — 여러 키를 순환할 때 잡아서 다음 키로 넘어가면 된다:

```python
from krx_fundamentals_client import DartQuotaExceededError, DartScraper

async def fetch_with_rotation(tickers, keys):
    for key in keys:
        scraper = DartScraper(api_key=key)
        try:
            return [await scraper.fetch_company(t) for t in tickers]
        except DartQuotaExceededError:
            continue
        finally:
            await scraper.close()
    raise RuntimeError("모든 키가 일한도를 소진했다")
```

## 아키텍처

```mermaid
flowchart LR
    Caller["호출자 코드"]

    subgraph Client["krx_fundamentals_client"]
        Dart["DartScraper\n(dart.py)"]
        Krx["KrxScraper\n(krx.py)"]
        Naver["NaverScraper\n(naver.py)"]
        Screen["screen_stocks / rank_stocks\n(screening.py, 순수 함수)"]
        Models["Pydantic 모델\n(models/schemas.py)"]
    end

    Dart -->|"corp_code 캐시(24h)"| DartAPI["DART OpenAPI\n기업개황·재무제표·배당·대주주·임원·발행주식수"]
    Krx -->|"OTP 2단계 다운로드"| KrxSite["KRX 정보데이터시스템\nPER·PBR·시가총액·섹터\n(⛔ 현재 로그인 차단)"]
    Naver --> NaverSite["네이버 금융 모바일 API\n시세·PER·PBR·EPS·BPS·배당수익률"]

    Caller --> Dart
    Caller --> Krx
    Caller --> Naver
    Caller --> Screen

    Krx -->|"list[InvestmentRatio]"| Screen
    Screen -->|"필터링/정렬 결과"| Caller

    Dart --> Models
    Krx --> Models
    Naver --> Models
    Models --> Caller
```

## 개발

```bash
uv sync --extra dev
uv run pytest                        # 테스트
uv run ruff check src/ tests/        # 린트
uv run ruff format src/ tests/       # 포맷
```

## 문서

- [docs/architecture.md](docs/architecture.md) — 스크레이퍼 구조, 랭킹/스크리닝, DART 호출 순서
- [docs/krx-blocked.md](docs/krx-blocked.md) — KRX 차단 코드 추적
- [`examples/`](examples/) — 바로 돌려볼 수 있는 사용 예제

## 라이선스

Apache-2.0 ([LICENSE](LICENSE))

## 만든 사람

**채영환 (Younghwan Chae)** · [GitHub @younghwan91](https://github.com/younghwan91) · [LinkedIn](https://www.linkedin.com/in/younghwan-chae/)

## 기여 및 이슈 제보

- 🐛 버그 제보, 질문, 기능 제안: [GitHub Issues](https://github.com/younghwan91/krx-fundamentals-client/issues)
- 📈 업데이트 소식: [팔로우 @younghwan91](https://github.com/younghwan91)


## 관련 프로젝트 — 오픈소스 퀀트 스택

한국·미국 주식과 암호화폐를 아우르는 오픈소스 스택입니다. 각 저장소는 독립적으로 쓸 수 있습니다.

| 축 | 프로젝트 | 설명 |
|---|---|---|
| 🇰🇷 한국 주식 | **[kiwoom-client](https://github.com/younghwan91/kiwoom-client)** | 키움증권 REST API Python 라이브러리 — 국내주식 엔드포인트 전수·실시간 WebSocket, sync + async (`pip install kiwoom-client`) |
| 🇰🇷 한국 주식 | **[krx-news-client](https://github.com/younghwan91/krx-news-client)** | 한국 주식 뉴스·공시를 한 스키마로 내주는 Python 클라이언트 라이브러리 (DART + 토스증권) |
| 🇰🇷 한국 주식 | **[krx-quant-core](https://github.com/younghwan91/krx-quant-core)** | 한국 주식 퀀트 시스템 공통 Python 코어 — KRX 호가·가격제한폭·세션 규칙, 시행일별 거래세 비용모델, 키움 주문 가드, DART 중대공시 위험 분류, 체결 시뮬레이션, Deflated Sharpe·purged CV 통계 |
| 🇰🇷 한국 주식 | **[fin-checkup](https://github.com/younghwan91/fin-checkup)** | 관심종목 위험 공시 텔레그램 알림 + DART·SEC 재무 건강검진 — 측정값과 사실만 전달한다 |
| 🇰🇷 한국 주식 | **[quant-airflow](https://github.com/younghwan91/quant-airflow)** | 시세·수급·실적을 TimescaleDB 로 수집하는 Airflow 파이프라인 — 상장폐지 종목까지 담아 생존편향을 막는다 |
| 🇰🇷 한국 주식 | **[swing-it](https://github.com/younghwan91/swing-it)** | 코스피·코스닥 알파 심사 프레임워크 — 개별 트레이드 분포로 판정하고 랜덤 음성대조·purged CV·Deflated Sharpe 를 CI 가드레일로 강제 |
| 🇺🇸 미국 주식 | **[portfolio-research](https://github.com/younghwan91/portfolio-research)** | 미국주식 팩터 엔진 — point-in-time·생존편향 보정 데이터 위에서 walk-forward 를 Deflated Sharpe·PBO 로 게이팅하고 ETF 전술배분도 같은 관문을 지난다 |
| 🇺🇸 미국 주식 | **[macro-sector-agent](https://github.com/younghwan91/macro-sector-agent)** | 하향식 미국 산업 사이클 리서치 — \"어느 산업이 잊혔나\"를 묻고 기계는 제외만 한다 |
| 🇺🇸 미국 주식 | **[automated-stock-trading-systems](https://github.com/younghwan91/automated-stock-trading-systems)** | Bensdorp 의 7개 비상관 트레이딩 시스템 백테스터 (교육용 재구현) |
| ₿ 암호화폐 | **[binance-quant-engine](https://github.com/younghwan91/binance-quant-engine)** | 암호화폐 선물 백테스트·실행 엔진 — 룩어헤드 0, 백테스트↔실거래 일체화 |
| ₿ 암호화폐 | **[crypto-quant-insights](https://github.com/younghwan91/crypto-quant-insights)** | 실거래 선물 시스템을 검증하며 나온 차트 연구 노트 — 폭락 스트레스 테스트·Kelly 레버리지·체결 간극 |

