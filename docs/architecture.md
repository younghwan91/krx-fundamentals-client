# 아키텍처

## 구조

```
┌──────────┐      ┌─────────────────┐      ┌───────────────────┐
│  Caller  │─────→│  Scraper 클래스  │─────→│  DART / KRX / 네이버 │
└──────────┘      └─────────────────┘      └───────────────────┘
```

상시 서버·캐시·백그라운드 스케줄러가 없다. 호출자가 스크레이퍼 메서드를 부르면 그때
소스에 직접 요청해 파싱된 결과를 즉시 반환한다.

| 소스 | 클래스 | 수집 단위 |
|-----|-------|----------|
| DART OpenAPI | [`DartScraper`](../src/krx_fundamentals_client/scrapers/dart.py) | 종목 단위 (호출마다 1개 티커) |
| KRX 정보데이터시스템 | [`KrxScraper`](../src/krx_fundamentals_client/scrapers/krx.py) | 시장 전체 벌크 CSV (OTP 2단계 다운로드) |
| 네이버 금융 모바일 API | [`NaverScraper`](../src/krx_fundamentals_client/scrapers/naver.py) | 종목 단위, 다수 종목은 `fetch_batch`로 순차 수집 |

## 랭킹 · 스크리닝

[`screening.py`](../src/krx_fundamentals_client/screening.py)의 `screen_stocks`/`rank_stocks`는
캐시나 상태를 갖지 않는 순수 함수다 — 호출자가 (보통 `KrxScraper.fetch_investment_ratios()`로
받은) `list[InvestmentRatio]`를 넘기면 그 자리에서 필터링/정렬해 반환한다. 시장 전체를 매번
다시 계산하므로, 반복 조회가 필요하면 호출자가 직접 결과를 보관해 재사용해야 한다.

## DART 호출 순서

기업 상세·재무제표·배당·대주주·임원 조회는 모두 `corp_code`(DART 고유번호)가 필요하다.
`DartScraper.fetch_company()` 등은 내부적으로 `_get_corp_code()`를 거치며, 이는 처음 호출 시
`load_corp_codes()`로 전체 매핑을 1회 내려받아 인스턴스에 캐시한다(24시간). 여러 종목을 조회할
계획이면 스크레이퍼 인스턴스를 재사용해 이 매핑을 재활용하는 편이 유리하다.

## 개발

### 테스트

```bash
pytest
pytest -v
pytest tests/test_models.py -v
```

### 린트 & 포맷

```bash
ruff check src/ tests/
ruff check --fix src/ tests/
ruff format src/ tests/
```
