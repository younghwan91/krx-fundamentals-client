# krx-fundamentals-api → krx-fundamentals-client 전환 설계

## 배경

`krx-fundamentals-api`는 DART·KRX·네이버에서 국내 기업 펀더멘탈을 모아
FastAPI + Redis + APScheduler 로 상시 서빙하는 REST 서버다. 그러나 README에
명시된 소비처(quant-airflow, kr-quant)를 직접 확인한 결과 둘 다 이 API를
실제로 호출하지 않는다 — quant-airflow는 코드 주석에서 계정 매핑 관례만
참조할 뿐 DART 수집을 자체 구현하고, kr-quant는 아예 참조가 없다. 로컬의
다른 레포들(README 하단 "관련 프로젝트" 표, `younghwan91/stack.yml`)에
나오는 언급도 전부 포트폴리오 소개용 링크이지 실제 의존이 아니다.

즉 상시 서버·Redis 캐시·APScheduler 스케줄러가 아무도 쓰지 않는 상태로
계속 운영 부담(배포, 헬스체크, 스케줄 잡 유지)만 만들고 있다. 자매
저장소 `krx-news-rest-api`가 동일한 문제로 이미 `krx-news-client`(순수
클라이언트 라이브러리)로 전환했고, `kiwoom-client`도 같은 형태다. 이
저장소도 같은 패턴으로 전환한다.

## 핵심 판단: 캐시 제거가 왜 문제가 안 되는가

`services/cache.py`의 `screen_stocks`/`get_ranking`은 이미 순수 함수다 —
Redis에서 읽어온 `list[InvestmentRatio]`를 필터링/정렬만 한다. 그리고
시장 전체 투자지표(`InvestmentRatio`)는 `KrxScraper`가 **OTP 2단계로
전 종목 CSV를 한 번에 받아오는 벌크 다운로드**로 수집한다 — 종목별
반복 호출이 아니다. 따라서 랭킹/스크리닝 같은 "시장 전체 집계" 기능도
캐시 없이 매 호출 시 벌크 CSV 1회 요청으로 그대로 재현 가능하다.

DART 쪽(`fetch_company`, `fetch_financials` 등)은 원래도 종목 단위 1회
호출이라 라이브러리 함수로 옮기는 데 문제가 없다. 유일하게 캐시가
필요했던 이유는 "상시 서버가 매 HTTP 요청마다 소스를 두드리지 않게"
하기 위함이었는데, 서버 자체가 없어지므로 그 이유도 함께 사라진다.

## 변경 범위

### 패키지/이름
- `src/krx_fundamentals_api` → `src/krx_fundamentals_client`
- `pyproject.toml`: `name = "krx-fundamentals-client"`, description을
  "국내 기업 펀더멘탈 Python 클라이언트 라이브러리"류로 변경
- GitHub 레포 rename은 사용자가 별도로 수행 (이 세션은 코드/문서만)

### 제거
- `main.py`, `routes/` (company.py, market.py), `services/cache.py`,
  `services/scheduler.py`, `config.py`(pydantic-settings 기반 설정)
- Redis 개념과 함께 무의미해지는 모델: `CrawlerStatus`, `DataSource`,
  `PaginatedResponse`
- `Dockerfile`, `docker-compose.yml`, `.env.example`
- 서버 전용 문서: `docs/api-examples.md`, `docs/images/swagger.png` 참조,
  `docs/architecture.md`의 캐시/스케줄러 서술 (KRX 차단 이슈 자체는
  `docs/krx-blocked.md`에 남기되 "API 엔드포인트가 빈다" 서술을
  "함수 호출이 빈 리스트를 반환한다"로 고침)
- 의존성: `fastapi`, `uvicorn[standard]`, `redis[hiredis]`, `apscheduler`,
  `pydantic-settings`. dev 쪽 `pytest-httpx`, `fakeredis`도 제거
- 테스트: `test_api.py`, `test_scheduler.py` 삭제 (대상 코드 삭제와 함께)

### 신규/이관
- `screening.py` (신규 모듈): `screen_stocks(ratios: list[InvestmentRatio], ...)`,
  `rank_stocks(ratios: list[InvestmentRatio], metric: RankingMetric, ascending=False)`
  — `services/cache.py`에서 페이지네이션(`page`/`page_size`)만 제거하고
  로직 그대로 이식. 반환 타입은 필터/정렬된 `list[InvestmentRatio]` 전체
  (슬라이싱은 호출자 책임)
- DART 스크레이퍼(`DartScraper`)에 `dart_api_key`를 생성자 인자로 받도록
  변경 (`config.settings.dart_api_key` 참조 제거)
- `__init__.py`에서 `DartScraper`, `KrxScraper`, `NaverScraper`,
  `screen_stocks`, `rank_stocks`, 모델들을 공개 API로 export

### 유지
- `scrapers/base.py`, `scrapers/dart.py`, `scrapers/krx.py`,
  `scrapers/naver.py` — 재시도/스로틀링 등 핵심 수집 로직 그대로
- `models/schemas.py`의 `Company`, `FinancialStatement`, `InvestmentRatio`,
  `Dividend`, `Shareholder`, `Executive`, `SectorOverview`, `Market`,
  `ReportType`, `RankingMetric`
- `tests/test_scrapers.py`, `tests/test_models.py` (입출력 인터페이스
  안 바뀌므로 대부분 그대로 유효 — import 경로만 갱신)

### examples/, README
- `examples/*.py`는 현재 `httpx.get("http://localhost:8010/...")` 형태의
  REST 클라이언트 코드 — 스크레이퍼 직접 호출(`await
  DartScraper(api_key=...).fetch_company(ticker)` 등) 방식으로 전면 재작성
- README/README.en.md: "REST API" 서술을 "Python 라이브러리"로,
  `docker compose up` 시작 가이드를 `pip install krx-fundamentals-client`
  + 코드 스니펫으로 교체. KRX 차단 경고는 유지(스크레이퍼 자체 이슈이므로)

## 테스트 전략
- `test_scrapers.py`, `test_models.py`: import 경로 갱신 외 변경 최소화,
  그대로 통과 확인
- `screening.py` 신규 테스트: 기존 `services/cache.py`의 screen_stocks/
  get_ranking 테스트가 있다면(test_api.py 안에 섞여 있을 가능성) 그
  케이스를 새 순수 함수 시그니처로 이식
- `ruff check` 통과, 전체 테스트 스위트 통과가 완료 기준

## 완료 기준
- FastAPI/Redis/APScheduler/pydantic-settings 의존성 0개
- `pip install -e .` 후 스크레이퍼 클래스 직접 import해서 호출 가능
- 전체 테스트 통과, ruff 통과
- README가 라이브러리 사용법을 정확히 반영
