# API 요청/응답 예시

[README](../README.md) 의 엔드포인트 표에 대응하는 전체 예시입니다. 서버가 `http://localhost:8010` 에 떠 있다고 가정합니다.

## 전체 기업 목록 조회

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

## 개별 기업 상세 정보

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

## 재무제표 조회

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

## 투자지표 조회

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

## 배당정보 조회

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

## 대주주 현황 조회

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

## 임원 현황 조회

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

## 시장 개요

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

## 섹터별 통계

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

## 랭킹 조회

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

## 종목 스크리닝

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

## 수집 상태 확인

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

## 에러 응답

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
