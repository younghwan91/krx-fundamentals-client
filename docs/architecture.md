# 아키텍처 · 캐시 · 운영

## 캐시 전략

아래 표는 [`services/cache.py`](../src/krx_fundamentals_api/services/cache.py)와 1:1로 대응한다.

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

## 환경변수

`.env` 파일 또는 환경변수로 설정합니다. `.env.example`을 복사하여 사용하세요.

```bash
cp .env.example .env
```

아래 표는 [`config.py`](../src/krx_fundamentals_api/config.py)의 `Settings` 와 1:1로 대응한다.

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
`Dockerfile` 의 `--host 0.0.0.0 --port 8000` 이고, 로컬 실행은 `uvicorn ... --port 8010`
([README 로컬 개발](../README.md#로컬-개발))이다. compose 의 redis 는 호스트 6389 에 매핑돼 있으므로,
로컬에서 그 Redis 를 쓸 때는 `REDIS_URL=redis://localhost:6389` 로 덮어써야 한다.

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
