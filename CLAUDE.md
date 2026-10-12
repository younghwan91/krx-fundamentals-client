# krx-fundamentals-client

DART·KRX·네이버에서 기업 펀더멘탈(재무제표·투자지표·배당·발행주식수·컨센서스)을 받아 Pydantic 모델로 돌려주는
**클라이언트 라이브러리**. 사용법은 `README.md`, 구조·DART 호출 순서는 `docs/architecture.md`.

## 명령

```bash
uv sync --extra dev
uv run pytest -q                  # ~50 tests, 1초 미만. HTTP 는 pytest-httpx 목
uv run ruff check src tests       # CI 와 같은 ruff==0.16.2 (핀은 의도 — a53d387)
uv lock --check                   # uv.lock 은 커밋한다
```

`ruff format` 은 CI 가 안 돈다. 지금 트리에 돌리면 8개 파일이 바뀐다 — 기능 커밋에 섞지 말고, 하려면 따로 커밋한다.

## 함정

- **KRX 경로(`KrxScraper`)는 막혀 있다(2026-08 실측).** OTP 가 `LOGOUT` 을 돌려주는데 검사를 통과해 **예외 없이 빈 리스트**가 된다.
  빈 결과를 "종목 없음"으로 읽지 말 것. 투자지표는 `NaverScraper` 로 부분 대체. 자세한 추적은 `docs/krx-blocked.md`.
- DART 일한도 소진은 `DartQuotaExceededError` 로 구분된다(빈 결과와 섞지 않는다). 키는 `~/git/quant-airflow/.env` 의
  `DART_API_KEY*` 를 Airflow 수집과 같이 쓴다 — 실 API 로 대량 호출은 사용자 확인 후에. 라이브러리는 환경변수를 읽지 않는다
  (`DartScraper(api_key=...)`; `examples/` 만 `DART_API_KEY` 를 읽는다).
- 레포 루트 `.env` 의 `REDIS_URL`·`CORS_ORIGINS` 는 서버 시절(fec1bcb 이전) 잔재다. 지금 코드는 쓰지 않는다.

## 설계 결정

- 서버가 아니다. FastAPI·캐시·스케줄러를 걷어내고 라이브러리로 바꿨다(fec1bcb, `docs/superpowers/specs/2026-09-05-client-library-refactor-design.md`).
  상태·저장은 호출자 몫이다. 다시 넣지 않는다.

## 소비자와 배포

- PyPI 에 **없다**(publish 워크플로도 없음). 유일한 소비자 quant-airflow 가 Docker 이미지에서
  `krx-fundamentals-client @ git+...@main` 으로 받는다 — **main 에 머지한 것이 다음 이미지 재빌드 때 그대로 들어간다.**
  quant-airflow `collectors/dart_earnings.py`·`dart_shares.py`·`dart_filing_dates.py`·`naver_consensus.py` 가 쓰는 공개 API
  (`DartScraper`·`DartQuotaExceededError`·`FinancialStatement`·`ReportType`·`NaverConsensusScraper`)의 시그니처·필드를 바꾸면 그쪽을 같이 확인한다.
- 공개 레포다. 커밋·README 에 키·사내 정보를 넣지 않는다.
