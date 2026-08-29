# KRX Fundamentals REST API

> A REST API that collects and serves fundamentals for Korean listed companies — financial statements, valuation ratios, dividends, screening

[![CI](https://github.com/younghwan91/krx-fundamentals-api/actions/workflows/ci.yml/badge.svg)](https://github.com/younghwan91/krx-fundamentals-api/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/github/license/younghwan91/krx-fundamentals-api)](https://github.com/younghwan91/krx-fundamentals-api/blob/main/LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-younghwan--chae-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/younghwan-chae/)

[한국어](README.md)

![Swagger UI](docs/images/swagger.png)

Pulls company fundamentals from DART, KRX and Naver Finance, normalizes them, and serves them over REST.

## Why cache-first

The upstream sources are slow, get blocked often, and rate-limit you. So collection and serving are
separate: a background scheduler (APScheduler) scrapes on an interval and writes to Redis, and the API
reads only from Redis. No request ever touches an external site, so latency stays flat and the last
snapshot keeps being served even when a source goes down.

> ⛔ **The KRX collection path is currently blocked (measured 2026-08).**
> KRX put a login in front of the MDCSTAT endpoints, and OTP issuance now returns `LOGOUT` instead of a
> token. The scraper treats that string as a valid OTP and passes it along, so it **collects 0 rows and
> raises nothing**. Everything KRX fills — valuation ratios, market cap, sectors — goes quietly empty,
> and so do `/ranking`, `/screening` and `/market/sectors`. (The top 100 tickers are backfilled from
> Naver. The DART path is unaffected.)
> Code walkthrough: [docs/krx-blocked.md](docs/krx-blocked.md) (Korean).

## Quick start

```bash
git clone https://github.com/younghwan91/krx-fundamentals-api.git
cd krx-fundamentals-api

cp .env.example .env    # set DART_API_KEY (required, free at https://opendart.fss.or.kr)
docker compose up -d    # API + Redis

curl http://localhost:8010/health   # {"status":"ok"}
open http://localhost:8010/docs     # Swagger UI
```

The container listens on 8000 and is mapped to host port 8010.

## Local development

Run Redis in a container and the API on the host.

```bash
uv sync --extra dev
docker compose up -d redis    # exposed on host port 6389

REDIS_URL=redis://localhost:6389 \
  uv run uvicorn krx_fundamentals_api.main:app --reload --port 8010
```

```bash
uv run pytest                        # tests run without Redis (fakeredis)
uv run ruff check src/ tests/        # lint
uv run ruff format src/ tests/       # format
```

The compose Redis is mapped to host 6389 so it does not collide with a Redis you may already have on
6379. If you run your own, the `.env` default (`redis://localhost:6379`) is correct as is.

| Variable | Default | Description |
|----------|---------|-------------|
| `DART_API_KEY` | — | **Required.** Free at [opendart.fss.or.kr](https://opendart.fss.or.kr) |
| `REDIS_URL` | `redis://localhost:6379` | `redis://redis:6379` under compose |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CORS_ORIGINS` | `["*"]` | Allowed origins |

Crawl-interval settings and the rest of the defaults are in [docs/architecture.md](docs/architecture.md) (Korean).

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/companies` | Company list (search, pagination) |
| `GET` | `/api/v1/companies/{ticker}` | Company detail |
| `GET` | `/api/v1/companies/{ticker}/financials` | Financials — 3 annual years from DART business reports |
| `GET` | `/api/v1/companies/{ticker}/ratios` | Valuation snapshot (PER, PBR, EPS, BPS, dividend yield) |
| `GET` | `/api/v1/companies/{ticker}/dividends` | Dividend history |
| `GET` | `/api/v1/companies/{ticker}/shareholders` | Major shareholders — ⚠️ no scheduler job exists, so **always empty** |
| `GET` | `/api/v1/companies/{ticker}/executives` | Executives — ⚠️ **always empty**, same reason |
| `GET` | `/api/v1/market/overview` | Sector list + collector status |
| `GET` | `/api/v1/market/sectors` | Per-sector stats — ⚠️ empty while KRX is blocked |
| `GET` | `/api/v1/ranking/{metric}` | Ranking by metric |
| `GET` | `/api/v1/screening` | Multi-condition screening |
| `GET` | `/api/v1/status` | Collection status (source × job) |
| `GET` | `/health` | Health check |

## Data sources

| Source | Data | Interval | Auth |
|--------|------|----------|------|
| [DART OpenAPI](https://opendart.fss.or.kr) | Company profile, financials, dividends | 24h | API key (required) |
| [KRX Information Data System](http://data.krx.co.kr) | PER, PBR, market cap, sectors | 1h | ⛔ Login required — collection currently broken |
| [Naver Finance](https://m.stock.naver.com) | Price, PER, PBR, EPS, BPS, dividend yield (**top 100 tickers only**) | 1h | None |

Without a DART key the company list itself stays empty, and the Naver backfill has no tickers to work with.

## Stack

FastAPI · httpx (async) · Redis · APScheduler · Pydantic · BeautifulSoup4 · Ruff · pytest + fakeredis · Docker

## Docs

- [docs/api-examples.md](docs/api-examples.md) — request/response examples per endpoint, full screening parameters
- [docs/architecture.md](docs/architecture.md) — cache keys and TTLs, collection pipeline, environment variables, Docker
- [docs/krx-blocked.md](docs/krx-blocked.md) — code walkthrough of the KRX block
- [`examples/`](examples/) — runnable Python client examples

(The docs under `docs/` are written in Korean.)

## License

Apache-2.0 ([LICENSE](LICENSE))

## Author

**Younghwan Chae** · [GitHub @younghwan91](https://github.com/younghwan91) · [LinkedIn](https://www.linkedin.com/in/younghwan-chae/)

Bugs and questions go to [Issues](https://github.com/younghwan91/krx-fundamentals-api/issues); a ⭐ helps if this was useful.

## Related projects — open-source quant stack

Korean and US equities plus crypto. Each repo stands on its own.

| Market | Project | Description |
|--------|---------|-------------|
| 🇰🇷 KR equities | **[kiwoom-rest-api](https://github.com/younghwan91/kiwoom-rest-api)** | Kiwoom Securities REST API Python client — full domestic-equity endpoint coverage, realtime WebSocket, sync + async (`pip install kiwoom-client`) |
| 🇰🇷 KR equities | **[krx-news-rest-api](https://github.com/younghwan91/krx-news-rest-api)** | Korean equity news and disclosure collection API (FastAPI + Redis) |
| 🇰🇷 KR equities | **[quant-airflow](https://github.com/younghwan91/quant-airflow)** | Airflow pipeline loading prices, flows and earnings into TimescaleDB — keeps delisted names to avoid survivorship bias |
| 🇰🇷 KR equities | **[kr-quant](https://github.com/younghwan91/kr-quant)** | KOSPI/KOSDAQ alpha research — walk-forward, random negative controls, purged CV and Deflated Sharpe enforced as CI guardrails |
| 🇺🇸 US equities | **[opt_portfolio](https://github.com/younghwan91/opt_portfolio)** | US factor engine — walk-forward on point-in-time, survivorship-corrected data, gated by Deflated Sharpe (+ VAA allocation backtester) |
| 🇺🇸 US equities | **[automated-stock-trading-systems](https://github.com/younghwan91/automated-stock-trading-systems)** | Backtester for Bensdorp's 7 non-correlated trading systems (educational reimplementation) |
| ₿ Crypto | **[quantbox-engine](https://github.com/younghwan91/quantbox-engine)** | Crypto futures backtest and execution engine — zero lookahead, backtest/live parity |
