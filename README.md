# 📊 KRX Fundamentals REST API

> 국내 기업 펀더멘탈 데이터를 수집·제공하는 REST API — 재무제표, 투자지표, 배당, 대주주, 종목 스크리닝

[![CI](https://github.com/younghwan91/krx-fundamentals-api/actions/workflows/ci.yml/badge.svg)](https://github.com/younghwan91/krx-fundamentals-api/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/github/license/younghwan91/krx-fundamentals-api)](https://github.com/younghwan91/krx-fundamentals-api/blob/main/LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-younghwan--chae-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/younghwan-chae/)

DART, KRX, 네이버 금융 등에서 기업 펀더멘탈 데이터를 자동 수집하여 정규화된 REST API로 제공합니다.

백그라운드 스케줄러가 주기적으로 데이터를 갱신하고 Redis에 캐싱하여, API 요청 시 즉시 응답하는 **캐시 우선(cache-first)** 아키텍처로 설계되었습니다.

> ⛔ **KRX 수집 경로는 현재 막혀 있다 (2026-08 실측).**
> KRX 정보데이터시스템이 MDCSTAT 계열에 회원 로그인을 걸면서, OTP 발급
> (`comm/fileDn/GenerateOTP/generate.cmd`)이 토큰 대신 문자열 `LOGOUT` 을 돌려준다.
> [`KrxScraper`](src/krx_fundamentals_api/scrapers/krx.py)는 그 `LOGOUT` 을 정상 OTP로 보고
> 그대로 다운로드 단계에 넘기므로 빈 CSV 를 받고 **예외 없이 빈 리스트를 반환**한다
> (`_get_otp` 는 비었는지와 500자 초과인지만 본다 — `scrapers/krx.py:94`, `LOGOUT` 은 6자라 통과한다).
> 그 결과 KRX 가 채우기로 되어 있는
> **투자지표(PER/PBR/배당수익률)·시가총액·섹터가 조용히 비어 있고**,
> `crawl_krx_ratios` 는 그런데도 예외가 안 났으니 성공으로 기록한다 —
> `update_crawler_status(..., len(all_ratios))` 를 error 없이 부르고
> (`services/scheduler.py:83`) `is_healthy = error is None` 이다 (`services/cache.py:304`).
> **0건 수집이 초록불로 남는다.** 여기에 얹힌 `/ranking`·`/screening`·`/market/sectors`도 함께 빈다.
> 상위 100종목 한정으로는 네이버 보조 수집이 `ratio:all` 을 채워 넣는다.
> DART 경로(기업개황·재무제표·배당)는 영향을 받지 않는다.

## 주요 기능

- 📑 **재무제표 조회** — DART 단일회사 주요계정 기준 매출액·영업이익·당기순이익·자산/부채/자본 총계 (현금흐름표는 수집하지 않는다)
- 📈 **투자지표 분석** — PER, PBR, EPS, BPS, 배당수익률, 시가총액 (ROE·ROA·부채비율·마진 필드는 스키마에만 있고 채우는 수집기가 아직 없다)
- 💰 **배당정보 제공** — 배당금, 배당수익률, 배당성향 이력 조회
- 👥 **대주주/임원 현황** — 최대주주 지분율, 임원 직위·담당업무·등기 여부 (보수 정보는 수집하지 않는다)
- 🔍 **종목 스크리닝** — PER, PBR, 배당수익률, 시가총액 등 복합 조건 필터링
- 🏆 **랭킹 조회** — 시가총액, PER, PBR, 배당수익률 기준별 종목 순위

---

## 빠른 시작

### Docker로 실행 (권장)

```bash
git clone https://github.com/younghwan91/krx-fundamentals-api.git
cd krx-fundamentals-api

cp .env.example .env          # 환경변수 설정
# .env 파일에서 DART_API_KEY 입력 (필수, https://opendart.fss.or.kr 에서 무료 발급)

docker compose up -d           # API 서버 + Redis 시작
```

```bash
# 헬스체크
curl http://localhost:8010/health
# {"status":"ok"}

# Swagger UI 확인
open http://localhost:8010/docs
```

### 로컬 개발 환경

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Redis 실행 (Docker)
docker compose up -d redis

# 개발 서버 실행 (자동 리로드)
uvicorn krx_fundamentals_api.main:app --reload --port 8010
```

서버가 시작되면 자동으로 DART, KRX 등에서 펀더멘탈 데이터 수집을 시작합니다.

---

## API 문서

서버 실행 후 **Swagger UI**에서 전체 API를 확인하고 테스트할 수 있습니다:
- Swagger UI: http://localhost:8010/docs
- ReDoc: http://localhost:8010/redoc

### 엔드포인트 목록

| 메서드 | 엔드포인트 | 설명 |
|-------|-----------|------|
| `GET` | `/api/v1/companies` | 전체 기업 목록 조회 |
| `GET` | `/api/v1/companies/{ticker}` | 개별 기업 상세 정보 |
| `GET` | `/api/v1/companies/{ticker}/financials` | 재무제표 (매출·영업이익·순이익·자산·부채·자본) |
| `GET` | `/api/v1/companies/{ticker}/ratios` | 투자지표 (PER, PBR, ROE 등) |
| `GET` | `/api/v1/companies/{ticker}/dividends` | 배당 이력 |
| `GET` | `/api/v1/companies/{ticker}/shareholders` | 대주주 현황 — ⚠️ 수집 잡이 스케줄러에 등록돼 있지 않아 항상 빈 목록 |
| `GET` | `/api/v1/companies/{ticker}/executives` | 임원 현황 — ⚠️ 수집 잡이 스케줄러에 등록돼 있지 않아 항상 빈 목록 |
| `GET` | `/api/v1/market/overview` | 섹터 목록 + 수집기 상태 |
| `GET` | `/api/v1/market/sectors` | 섹터별 통계 |
| `GET` | `/api/v1/ranking/{metric}` | 지표별 종목 랭킹 |
| `GET` | `/api/v1/screening` | 복합 조건 종목 스크리닝 |
| `GET` | `/api/v1/status` | 데이터 수집 상태 (소스×잡 단위) |
| `GET` | `/health` | 헬스체크 |

### 요청/응답 예시

#### 전체 기업 목록 조회

`q`(회사명·종목코드 검색), `page`, `page_size`(기본 50, 최대 200)만 받는다 — 시장·섹터 필터는 이 엔드포인트에 없다(스크리닝 쪽에 있다).

```bash
curl "http://localhost:8010/api/v1/companies?q=삼성&page=1&page_size=2"
```

응답은 `PaginatedResponse` 이고 `items` 는 기업 개황(`Company`)이다. 투자지표는 여기 들어가지 않는다.

```json
{
  "items": [
    {
      "ticker": "005930",
      "corp_code": "00126380",
      "name": "삼성전자",
      "name_en": "SAMSUNG ELECTRONICS CO,.LTD",
      "market": "kospi",
      "sector": "",
      "industry": "264",
      "ceo": "한종희",
      "address": "경기도 수원시 영통구 삼성로 129",
      "phone": "",
      "website": "www.samsung.com/sec",
      "ir_url": "",
      "established_date": "19690113",
      "listing_date": "",
      "fiscal_month": 12,
      "updated_at": "2026-03-31T10:00:00"
    }
  ],
  "total": 2424,
  "page": 1,
  "page_size": 2,
  "has_next": true
}
```

> `sector`·`phone`·`listing_date` 는 DART 기업개황(`company.json`)에서 채우는 코드가 없어 항상 빈 문자열이다
> (`scrapers/dart.py:204`). `industry` 는 업종명이 아니라 DART `induty_code` 값이다.

#### 개별 기업 상세 정보

```bash
curl "http://localhost:8010/api/v1/companies/005930"
```

목록의 `items` 원소와 같은 `Company` 객체를 그대로 돌려준다. 없으면 `404`.

```json
{
  "ticker": "005930",
  "corp_code": "00126380",
  "name": "삼성전자",
  "name_en": "SAMSUNG ELECTRONICS CO,.LTD",
  "market": "kospi",
  "sector": "",
  "industry": "264",
  "ceo": "한종희",
  "address": "경기도 수원시 영통구 삼성로 129",
  "phone": "",
  "website": "www.samsung.com/sec",
  "ir_url": "",
  "established_date": "19690113",
  "listing_date": "",
  "fiscal_month": 12,
  "updated_at": "2026-03-31T10:00:00"
}
```

#### 재무제표 조회

쿼리 파라미터는 없다. 스케줄러가 **사업보고서(연간)** 만 최근 3개 연도치 수집해 캐싱하므로, 분기 데이터는 아직 들어오지 않는다.

```bash
curl "http://localhost:8010/api/v1/companies/005930/financials"
```

```json
{
  "ticker": "005930",
  "statements": [
    {
      "ticker": "005930",
      "year": 2025,
      "report_type": "annual",
      "currency": "KRW",
      "revenue": 302231000000000,
      "operating_income": 36183000000000,
      "net_income": 26401000000000,
      "total_assets": 455905000000000,
      "total_liabilities": 106151000000000,
      "total_equity": 349754000000000,
      "revenue_yoy": null,
      "operating_income_yoy": null,
      "net_income_yoy": null,
      "collected_at": "2026-03-31T09:00:12"
    }
  ],
  "total": 3
}
```

> 소스는 DART `fnlttSinglAcnt.json`(단일회사 주요계정)이라 **현금흐름표 항목은 없다**.
> `*_yoy` 필드는 스키마에만 있고 계산하는 코드가 없어 항상 `null` 이다.

#### 투자지표 조회

```bash
curl "http://localhost:8010/api/v1/companies/005930/ratios"
```

연도별 배열이 아니라 **현재 스냅샷 한 건**(`InvestmentRatio`)이다. 없으면 `404`.

```json
{
  "ticker": "005930",
  "name": "삼성전자",
  "market": "kospi",
  "market_cap": 3580000,
  "per": 12.5,
  "pbr": 1.18,
  "psr": null,
  "pcr": null,
  "eps": 4800,
  "bps": 50817,
  "roe": null,
  "roa": null,
  "debt_ratio": null,
  "operating_margin": null,
  "net_margin": null,
  "dividend_yield": 2.34,
  "price": 70000,
  "volume": 12345678,
  "high_52w": 88800,
  "low_52w": 49900,
  "foreign_ratio": 53.12,
  "updated_at": "2026-03-31T10:00:00"
}
```

> `market_cap` 단위는 **억원**이다. `roe`·`roa`·`debt_ratio`·`operating_margin`·`net_margin`·`psr`·`pcr` 는
> 어느 수집기도 채우지 않아 항상 `null` 이다.

#### 배당정보 조회

```bash
curl "http://localhost:8010/api/v1/companies/005930/dividends"
```

```json
{
  "ticker": "005930",
  "dividends": [
    {
      "ticker": "005930",
      "year": 2025,
      "dividend_per_share": 1444,
      "dividend_yield": 2.34,
      "payout_ratio": 30.1,
      "total_dividends": null,
      "ex_dividend_date": "",
      "payment_date": "",
      "collected_at": "2026-03-31T09:00:12"
    }
  ],
  "total": 4
}
```

> `total_dividends`·`ex_dividend_date`·`payment_date` 는 DART `alotDvdnd.json` 파싱에서 채우지 않아 비어 있다
> (`scrapers/dart.py:333`).

#### 대주주 현황 조회

```bash
curl "http://localhost:8010/api/v1/companies/005930/shareholders"
```

⚠️ `DartScraper.fetch_shareholders` 는 구현돼 있지만 **스케줄러에 등록된 잡이 없어** 캐시가 채워지지 않는다
(`services/scheduler.py:start_scheduler`). 따라서 현재는 항상 빈 목록이다.

```json
{
  "ticker": "005930",
  "shareholders": [],
  "total": 0
}
```

캐시가 채워질 경우의 원소 형태(`Shareholder`)는 다음과 같다 — 직위(`position`) 필드는 없다.

```json
{
  "ticker": "005930",
  "name": "이재용",
  "shares": 16530000,
  "ownership_pct": 0.28,
  "change_shares": 0,
  "report_date": "2025",
  "collected_at": "2026-03-31T09:00:12"
}
```

#### 임원 현황 조회

```bash
curl "http://localhost:8010/api/v1/companies/005930/executives"
```

⚠️ 대주주와 같은 이유로 수집 잡이 없어 현재는 항상 빈 목록이다.

```json
{
  "ticker": "005930",
  "executives": [],
  "total": 0
}
```

캐시가 채워질 경우의 원소 형태(`Executive`)다 — **보수(compensation)·보유주식수 필드는 없다**.

```json
{
  "ticker": "005930",
  "name": "한종희",
  "birth_year": "1962년 08월",
  "gender": "남",
  "position": "대표이사 부회장",
  "role": "DX부문장",
  "tenure": "2026년 03월",
  "is_registered": true,
  "collected_at": "2026-03-31T09:00:12"
}
```

#### 시장 개요

```bash
curl "http://localhost:8010/api/v1/market/overview"
```

시장(KOSPI/KOSDAQ)별 집계가 아니라 **섹터 목록과 수집기 상태**를 합쳐 돌려준다.

```json
{
  "sectors": [
    { "sector": "음식료품", "company_count": 0, "total_market_cap": 42500000000000,
      "avg_per": null, "avg_pbr": null, "avg_dividend_yield": null }
  ],
  "crawler_status": [
    { "source": "dart", "job_name": "companies", "last_crawled_at": "2026-03-31T09:00:12",
      "items_count": 2424, "is_healthy": true, "error": null }
  ]
}
```

#### 섹터별 통계

```bash
curl "http://localhost:8010/api/v1/market/sectors"
```

```json
{
  "sectors": [
    {
      "sector": "음식료품",
      "company_count": 0,
      "total_market_cap": 42500000000000,
      "avg_per": null,
      "avg_pbr": null,
      "avg_dividend_yield": null
    }
  ],
  "total": 33
}
```

> 소스는 KRX 업종별 시세(MDCSTAT03901)이고, 수집기가 채우는 값은 `sector` 와 `total_market_cap` 둘뿐이다
> (`scrapers/krx.py:320`). `company_count`·`avg_*` 는 기본값 그대로다. 게다가 KRX 경로가 막혀 있어
> 현재는 이 목록 자체가 비어 있다.

#### 랭킹 조회

파라미터는 `page`, `page_size`(기본 20, 최대 100), `ascending`(불리언, 기본 `false`)이다 — `order`·`limit` 은 없다.

```bash
# 시가총액 상위 종목
curl "http://localhost:8010/api/v1/ranking/market_cap?page_size=5"

# PER 하위 종목 (저PER)
curl "http://localhost:8010/api/v1/ranking/per?ascending=true&page_size=5"

# 배당수익률 상위 종목
curl "http://localhost:8010/api/v1/ranking/dividend_yield?page_size=5"
```

응답은 다른 목록 엔드포인트와 같은 `PaginatedResponse` 이고, `items` 는 `InvestmentRatio` 전체 객체다
(`rank`·`value` 같은 필드는 없다).

```json
{
  "items": [
    { "ticker": "005930", "name": "삼성전자", "market": "kospi",
      "market_cap": 3580000, "per": 12.5, "pbr": 1.18, "dividend_yield": 2.34,
      "updated_at": "2026-03-31T10:00:00" }
  ],
  "total": 812,
  "page": 1,
  "page_size": 5,
  "has_next": true
}
```

**사용 가능한 랭킹 지표:**

| metric | 설명 |
|--------|------|
| `market_cap` | 시가총액 |
| `per` | PER (주가수익비율) |
| `pbr` | PBR (주가순자산비율) |
| `roe` | ROE (자기자본이익률) — 값이 수집되지 않아 결과가 항상 비어 있다 |
| `dividend_yield` | 배당수익률 |
| `revenue` | 매출액 — ⚠️ 정렬 매핑에 없어 **시가총액 순으로 반환된다** (`services/cache.py:274`) |
| `net_income` | 당기순이익 — ⚠️ 위와 동일 |

> `operating_income` 은 `RankingMetric` 열거형에 없어 `422` 가 난다.

#### 종목 스크리닝

`market` 값은 **소문자** `kospi` / `kosdaq` 다 (`Market` 열거형 값과 그대로 비교한다 — `services/cache.py:233`).

```bash
# 저PER + 고배당 KOSPI 종목
curl "http://localhost:8010/api/v1/screening?market=kospi&per_max=10&dividend_yield_min=3&page_size=5"
```

```json
{
  "items": [
    { "ticker": "005380", "name": "현대차", "market": "kospi",
      "market_cap": 520000, "per": 5.2, "pbr": 0.65, "dividend_yield": 3.81,
      "updated_at": "2026-03-31T10:00:00" }
  ],
  "total": 47,
  "page": 1,
  "page_size": 5,
  "has_next": true
}
```

#### 수집 상태 확인

```bash
curl "http://localhost:8010/api/v1/status"
```

소스별 한 건이 아니라 **소스 × 잡** 단위로 기록된다(`crawler:status:{source}:{job}`).

```json
[
  {
    "source": "dart",
    "job_name": "companies",
    "last_crawled_at": "2026-03-31T09:00:12",
    "items_count": 2424,
    "is_healthy": true,
    "error": null
  },
  {
    "source": "krx",
    "job_name": "ratios",
    "last_crawled_at": "2026-03-31T10:00:05",
    "items_count": 0,
    "is_healthy": true,
    "error": null
  },
  {
    "source": "naver",
    "job_name": "supplement",
    "last_crawled_at": "2026-03-31T10:00:08",
    "items_count": 100,
    "is_healthy": true,
    "error": null
  }
]
```

> 위 `krx` 행이 `items_count=0` 이면서 `is_healthy=true` 인 것이 바로 앞서 말한 **조용한 실패**다.

### 에러 응답

| 상태 코드 | 의미 | 예시 |
|----------|------|------|
| `200` | 성공 | 정상 응답 |
| `404` | 종목 없음 | `{"detail": "Company 999999 not found"}` |
| `422` | 유효성 검증 실패 | 필수 파라미터 누락, 잘못된 값 |
| `503` | Redis 연결 실패 | `{"detail": "Cache service unavailable"}` |
| `500` | 서버 내부 에러 | `{"detail": "Internal server error"}` |

---

## 스크리닝 파라미터

`GET /api/v1/screening` 엔드포인트에서 사용 가능한 필터 파라미터입니다. 모든 파라미터는 선택 사항이며, 조합하여 사용할 수 있습니다.

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `market` | `string` | — | 시장 필터 — **소문자** `kospi`, `kosdaq` |
| `sector` | `string` | — | 섹터 필터 — ⚠️ `Company.sector` 를 채우는 수집기가 없어 이 필터를 쓰면 결과가 항상 0건이다 |
| `per_min` | `float` | — | PER 최소값 |
| `per_max` | `float` | — | PER 최대값 |
| `pbr_min` | `float` | — | PBR 최소값 |
| `pbr_max` | `float` | — | PBR 최대값 |
| `roe_min` | `float` | — | ROE 최소값 (%) — ⚠️ `roe` 를 채우는 수집기가 없어 결과가 항상 0건이다 |
| `dividend_yield_min` | `float` | — | 배당수익률 최소값 (%) |
| `market_cap_min` | `float` | — | 최소 시가총액 (**억원**) |
| `page` | `int` | `1` | 페이지 번호 |
| `page_size` | `int` | `20` | 페이지 크기 (최대 100) |

**사용 예시:**

```bash
# 저PBR 가치주 스크리닝
curl "http://localhost:8010/api/v1/screening?pbr_max=1.0"

# KOSDAQ 종목 중 시총 1조(=10,000억) 이상
curl "http://localhost:8010/api/v1/screening?market=kosdaq&market_cap_min=10000"

# 배당주 스크리닝: PER 10 이하, 배당수익률 3% 이상
curl "http://localhost:8010/api/v1/screening?per_max=10&dividend_yield_min=3"
```

---

## 데이터 소스

| 소스 | URL | 데이터 | 갱신 주기 | 인증 |
|-----|-----|-------|----------|------|
| **DART OpenAPI** | [opendart.fss.or.kr](https://opendart.fss.or.kr) | 기업개황, 재무제표, 배당 (대주주·임원은 수집기만 있고 스케줄 잡이 없다) | 매일 | API 키 (필수) |
| **KRX 정보데이터시스템** | [data.krx.co.kr](http://data.krx.co.kr) | PER, PBR, 시가총액, 섹터 | 1시간 | ⛔ **회원 로그인 필요 — 현재 수집 불가** (OTP 가 `LOGOUT` 반환, 2026-08 실측) |
| **네이버 금융** | [m.stock.naver.com](https://m.stock.naver.com) | 시세·PER·PBR·EPS·BPS·배당수익률·외국인비율·52주 고저 (**상위 100종목만**) | 1시간 | 불필요 |

> **참고:** DART API 키는 [opendart.fss.or.kr](https://opendart.fss.or.kr)에서 무료 발급 가능합니다. 키가 없으면 기업개황·재무제표·배당 데이터를 수집할 수 없고, 기업 목록이 비어 있으므로 네이버 보조 수집도 대상 종목을 찾지 못합니다.

---

## 캐시 전략

아래 표는 [`services/cache.py`](src/krx_fundamentals_api/services/cache.py)와 1:1로 대응한다.

| 데이터 | Redis 구조 | TTL | 키 패턴 |
|-------|-----------|-----|---------|
| 기업 목록·상세 | Hash (필드 = 종목코드) | 24시간 | `company:all` |
| 재무제표 | String (JSON) | 24시간 | `financial:{ticker}` |
| 투자지표 (목록·개별) | Hash (필드 = 종목코드) | 1시간 | `ratio:all` |
| 배당 이력 | String (JSON) | 24시간 | `dividend:{ticker}` |
| 대주주 현황 | String (JSON) | 24시간 | `shareholder:{ticker}` |
| 임원 현황 | String (JSON) | 24시간 | `executive:{ticker}` |
| 섹터 통계 | String (JSON) | 1시간 | `sector:all` |
| 수집 상태 | String (JSON) | 없음 | `crawler:status:{source}:{job}` |

기업 상세·투자지표 개별 조회는 별도 키가 아니라 위 Hash 의 필드를 `HGET` 한다.

**캐시하지 않는 것:**

- **랭킹** — Sorted Set 을 쓰지 않는다. `ratio:all` 을 전부 읽어 매 요청마다 파이썬에서 정렬한다 (`get_ranking`).
- **스크리닝** — 결과를 저장하지 않는다. 마찬가지로 매 요청마다 `ratio:all` 전체를 훑는다 (`screen_stocks`).
  `SCREENING_TTL = 300` 상수는 선언만 돼 있고 쓰이는 곳이 없다.
- **시장 개요** — 전용 키가 없다. `sector:all` 과 `crawler:status:*` 를 읽어 조립해 돌려준다.

---

## 아키텍처

```
┌──────────────────────────────────────────────────────────────────────┐
│                          FastAPI 서버                                 │
│                                                                       │
│  ┌─────────┐      ┌────────────────┐      ┌────────┐                │
│  │ Client  │─────→│  Routes (API)  │─────→│ Redis  │ ← 즉시 응답    │
│  └─────────┘      └────────────────┘      └───┬────┘                │
│                                                │                      │
│  ┌─────────────────────────────────────────────┘                      │
│  │  백그라운드 데이터 수집 (APScheduler)                                │
│  │                                                                    │
│  │  ┌───────────────────┐    ┌────────────┐    ┌────────┐           │
│  │  │   Data Collectors │───→│  정규화/파싱 │───→│ Redis  │           │
│  │  │                   │    └────────────┘    └────────┘           │
│  │  │ · DART OpenAPI    │                                            │
│  │  │ · KRX 정보데이터   │  DART: 24시간 간격                         │
│  │  │ · 네이버 금융      │  KRX/네이버: 1시간 간격                     │
│  │  └───────────────────┘                                            │
│  └────────────────────────────────────────────────────────────────────│
└──────────────────────────────────────────────────────────────────────┘
```

### 데이터 흐름

1. **서버 시작** → DART 체인(고유번호 → 기업개황 → 재무제표 → 배당)을 의존성 순서대로 1회 실행하고, KRX 투자지표도 1회 실행한다. 네이버 보조는 초기 잡이 없어 첫 1시간 뒤부터 돈다.
2. **스케줄러** → APScheduler `interval` 잡이다. 고정 시각(cron)이 아니라 **기동 시점 기준 경과 시간**으로 반복한다 — DART 계열 24시간, KRX/네이버 1시간 (`CRAWL_INTERVAL_*` 로 조절)
3. **컬렉터** → API 호출 또는 HTML 파싱으로 원본 데이터 수집
4. **정규화** → 기업 정보, 재무제표, 투자지표 등을 통일 스키마로 변환
5. **Redis 저장** → Hash 와 String 두 가지 구조로 캐싱
6. **API 응답** → Redis에서 직접 읽어 즉시 반환

---

## 예제 코드

`examples/` 디렉토리에 바로 실행 가능한 예제가 포함되어 있습니다.

| 파일 | 설명 |
|------|------|
| [`basic_usage.py`](examples/basic_usage.py) | 기본 사용법 — 기업 조회, 재무제표, 투자지표 |
| [`screening.py`](examples/screening.py) | 종목 스크리닝 — 가치주/배당주/성장주 필터링 |
| [`portfolio_analysis.py`](examples/portfolio_analysis.py) | 포트폴리오 분석 — 복수 종목 펀더멘탈 비교 |

```bash
# 서버 실행 후
pip install httpx
python examples/basic_usage.py
```

---

## 환경변수

`.env` 파일 또는 환경변수로 설정합니다. `.env.example`을 복사하여 사용하세요.

```bash
cp .env.example .env
```

아래 표는 [`config.py`](src/krx_fundamentals_api/config.py)의 `Settings` 와 1:1로 대응한다.

| 변수 | 기본값 | 필수 | 설명 |
|-----|-------|------|------|
| `REDIS_URL` | `redis://localhost:6379` | — | Redis 연결 URL. **Docker 로 띄우면 `redis://redis:6379`** (compose 서비스 이름) |
| `DART_API_KEY` | — | ✅ | DART Open API 키 ([발급](https://opendart.fss.or.kr)) |
| `CRAWL_INTERVAL_MASTER` | `86400` | — | 종목마스터 수집 주기 (초, 기본 24시간) |
| `CRAWL_INTERVAL_FINANCIALS` | `86400` | — | 재무제표 수집 주기 (초, 기본 24시간) |
| `CRAWL_INTERVAL_RATIOS` | `3600` | — | 투자지표 수집 주기 (초, 기본 1시간) |
| `LOG_LEVEL` | `INFO` | — | 로그 레벨 (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `CORS_ORIGINS` | `["*"]` | — | CORS 허용 origin 목록 |

서버 바인드 주소·포트·워커 수는 환경변수가 아니라 실행 명령에서 정한다 — 컨테이너는
`Dockerfile` 의 `--host 0.0.0.0 --port 8000`, 로컬은 위 `uvicorn ... --port 8010` 이다.

---

## 개발

### 테스트

```bash
# 전체 테스트 (Redis 불필요 — fakeredis로 자동 mock)
pytest

# 상세 출력
pytest -v

# 단일 테스트
pytest tests/test_api.py::test_health -v

# 특정 파일
pytest tests/test_models.py -v
```

### 린트 & 포맷

```bash
# 린트 검사
ruff check src/ tests/

# 자동 수정
ruff check --fix src/ tests/

# 코드 포맷팅
ruff format src/ tests/
```

### Docker 빌드

```bash
# 이미지 빌드
docker build -t krx-fundamentals-api .

# 단독 실행
docker run -p 8010:8000 --env-file .env krx-fundamentals-api

# Docker Compose (권장)
docker compose up -d           # 시작
docker compose logs -f api     # 로그 확인
docker compose down            # 중지
```

---

## 생태계

이 프로젝트는 한국 주식시장 데이터 인프라의 일부로, 아래 API들과 함께 사용할 수 있습니다.

```
┌─────────────────────────────────────────────────────────────┐
│                    한국 주식시장 데이터 인프라                   │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │  kiwoom-rest-api │  │krx-news-rest-api│  │    krx-     │ │
│  │                  │  │                 │  │fundamentals-│ │
│  │  매매 실행 + 시세  │  │  뉴스 + 공시     │  │    api      │ │
│  │  주문, 잔고, 체결  │  │  KIND, DART,    │  │             │ │
│  │  호가, 체결가     │  │  네이버, 한경,   │  │ 재무제표,    │ │
│  │                  │  │  더벨           │  │ 투자지표,    │ │
│  │                  │  │                 │  │ 배당, 스크리닝│ │
│  └─────────────────┘  └─────────────────┘  └──────┬──────┘ │
│                                                ← 현재 │       │
└─────────────────────────────────────────────────────────────┘
```

| 저장소 | 역할 | 포트 |
|-------|------|------|
| [kiwoom-rest-api](https://github.com/younghwan91/kiwoom-rest-api) | 매매 실행 + 실시간 시세 | — (서버가 아니라 pip 라이브러리 `kiwoom-client`) |
| [krx-news-rest-api](https://github.com/younghwan91/krx-news-rest-api) | 뉴스 / 공시 수집 | `8000` |
| **krx-fundamentals-api** | 기업 펀더멘탈 데이터 ← 현재 | `8010` |

---

## 기술 스택

| 구성 요소 | 기술 |
|----------|------|
| 프레임워크 | [FastAPI](https://fastapi.tiangolo.com/) |
| HTTP 클라이언트 | [httpx](https://www.python-httpx.org/) (async) |
| HTML 파싱 | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) + lxml |
| 캐시 | [Redis](https://redis.io/) (redis-py async) |
| 스케줄러 | [APScheduler](https://apscheduler.readthedocs.io/) |
| 데이터 검증 | [Pydantic](https://docs.pydantic.dev/) |
| 설정 관리 | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| 린트/포맷 | [Ruff](https://docs.astral.sh/ruff/) |
| 테스트 | [pytest](https://pytest.org/) + fakeredis |
| CI/CD | GitHub Actions |
| 컨테이너 | Docker + docker-compose |

---

## 라이선스

Apache-2.0 ([LICENSE](LICENSE))


---

## ⭐ 도움이 되셨다면

이 프로젝트가 유용했다면 우측 상단 **[⭐ Star](https://github.com/younghwan91/krx-fundamentals-api)** 를 눌러주세요. 검색·추천 노출이 올라가 더 많은 분들이 찾을 수 있습니다.

- 🐛 버그·질문 → [Issues](https://github.com/younghwan91/krx-fundamentals-api/issues)
- 📈 업데이트 소식 → [팔로우 @younghwan91](https://github.com/younghwan91)

## 관련 프로젝트 — 오픈소스 퀀트 스택

한국·미국 주식과 암호화폐를 아우르는 오픈소스 스택입니다. 각 저장소는 독립적으로 쓸 수 있습니다.

| 축 | 프로젝트 | 설명 |
|---|---|---|
| 🇰🇷 한국 주식 | **[kiwoom-rest-api](https://github.com/younghwan91/kiwoom-rest-api)** | 키움증권 REST API Python 라이브러리 — 국내주식 엔드포인트 전수·실시간 WebSocket, sync + async (`pip install kiwoom-client`) |
| 🇰🇷 한국 주식 | **[krx-news-rest-api](https://github.com/younghwan91/krx-news-rest-api)** | 한국 주식 뉴스·공시 수집 REST API (FastAPI + Redis) |
| 🇰🇷 한국 주식 | **[quant-airflow](https://github.com/younghwan91/quant-airflow)** | 시세·수급·실적을 TimescaleDB 로 수집하는 Airflow 파이프라인 — 상장폐지 종목까지 담아 생존편향을 막는다 |
| 🇰🇷 한국 주식 | **[kr-quant](https://github.com/younghwan91/kr-quant)** | 코스피·코스닥 알파 리서치 — walk-forward·랜덤 음성대조·purged CV·Deflated Sharpe 를 CI 가드레일로 강제 |
| 🇺🇸 미국 주식 | **[opt_portfolio](https://github.com/younghwan91/opt_portfolio)** | 미국주식 팩터 엔진 — point-in-time·생존편향 보정 데이터 위에서 walk-forward 를 Deflated Sharpe 로 게이팅 (+ VAA 자산배분 백테스터) |
| 🇺🇸 미국 주식 | **[automated-stock-trading-systems](https://github.com/younghwan91/automated-stock-trading-systems)** | Bensdorp 의 7개 비상관 트레이딩 시스템 백테스터 (교육용 재구현) |
| ₿ 암호화폐 | **[quantbox-engine](https://github.com/younghwan91/quantbox-engine)** | 암호화폐 선물 백테스트·실행 엔진 — 룩어헤드 0, 백테스트↔실거래 일체화 |

## 만든 사람

**채영환 (Younghwan Chae)** · [GitHub @younghwan91](https://github.com/younghwan91) · [LinkedIn](https://www.linkedin.com/in/younghwan-chae/)

전체 오픈소스 퀀트 스택은 [프로필](https://github.com/younghwan91)에서 한눈에 볼 수 있습니다.
