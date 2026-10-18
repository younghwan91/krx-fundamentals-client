# krx-fundamentals-client

**Korean corporate fundamentals from DART, KRX and Naver as Pydantic models — a Python library, no server, one pip line.**

[![CI](https://github.com/younghwan91/krx-fundamentals-client/actions/workflows/ci.yml/badge.svg)](https://github.com/younghwan91/krx-fundamentals-client/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/younghwan91/krx-fundamentals-client)](https://github.com/younghwan91/krx-fundamentals-client/blob/main/LICENSE)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-younghwan--chae-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/younghwan-chae/)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/hero-dark.png">
  <img alt="Eight years of Samsung Electronics consolidated revenue and operating income and the dividend from DART, plus PER, PBR and dividend yield from Naver, fetched through the library into one schema" src="docs/images/hero-light.png" width="100%">
</picture>

[한국어](README.md)

- Every number above is a library return value or a ratio of two (operating margin): Samsung Electronics consolidated statements FY2018 to FY2025 from `fetch_financials`, the dividend per share from `fetch_dividends`, PER, PBR and dividend yield from `NaverScraper.fetch_stock_info` ([hero-data.json](docs/images/hero-data.json)).
- No standing server, cache or scheduler. Four dependencies (httpx, beautifulsoup4, lxml, pydantic); each call hits the source directly.
- A spent DART daily quota raises `DartQuotaExceededError`, so it never masquerades as "no data".

> ⛔ **The KRX path is blocked (measured 2026-08).** KRX put a login in front of its endpoints and `KrxScraper` now returns an empty list without raising.
> The DART path is unaffected; per-ticker price and valuation ratios (PER, PBR, ...) come from `NaverScraper`. Walkthrough: [docs/krx-blocked.md](docs/krx-blocked.md) (Korean).

## Quick start

Not on PyPI yet; install from git:

```bash
pip install git+https://github.com/younghwan91/krx-fundamentals-client
```

Get a free DART key at [opendart.fss.or.kr](https://opendart.fss.or.kr). Eight years of one company's statements, exactly what the hero shows:

```python
import asyncio
from krx_fundamentals_client import DartScraper

async def main():
    dart = DartScraper(api_key="...")
    try:
        company = await dart.fetch_company("005930")
        print(company.name, company.ceo)
        for year in range(2018, 2026):
            fs = await dart.fetch_financials("005930", year)   # annual report, consolidated first (separate as fallback)
            if fs:
                print(year, f"revenue {fs.revenue:,.0f}", f"operating income {fs.operating_income:,.0f}")
    finally:
        await dart.close()

asyncio.run(main())
```

Runnable scripts live in [`examples/`](examples/).

## What it does

| Source | Class | Returns | Unit of collection | Auth |
|--------|-------|---------|--------------------|------|
| [DART OpenAPI](https://opendart.fss.or.kr) | `DartScraper` | Company profile, financial statements (annual, half, quarterly), shares outstanding, dividends, major shareholders, executives | Per ticker; statements also via `fetch_financials_batch`, up to 100 tickers per call | API key (free) |
| [Naver Finance](https://m.stock.naver.com) | `NaverScraper` | One `InvestmentRatio`: price, market cap, PER, PBR, EPS, BPS, dividend yield, volume, 52-week high/low, foreign ownership (measured 2026-10). Accounting ratios such as ROE and debt ratio are not provided and stay `None` | Per ticker; `fetch_batch` for many | None |
| [KRX Information Data System](http://data.krx.co.kr) | `KrxScraper` | PER, PBR, market cap, sectors | Whole-market bulk CSV | None (⛔ currently blocked) |

- **Models**: `Company`, `FinancialStatement`, `SharesOutstanding`, `InvestmentRatio`, `Dividend`, `Shareholder`, `Executive`, `SectorOverview`. All Pydantic, importable from `krx_fundamentals_client`. Fields in [`models/schemas.py`](src/krx_fundamentals_client/models/schemas.py).
- **Screening and ranking**: `screen_stocks` (range filters on PER, PBR, ROE, dividend yield, market cap) and `rank_stocks` (sort by a `RankingMetric`). Pure functions over a `list[InvestmentRatio]`, no state.
- Numeric fields on every model are optional: when a source does not provide an item, it stays `None` rather than being invented.

## Why it is built this way

- **It is not a server.** FastAPI, cache and scheduler were removed in favor of a library; state and storage belong to the caller. Same shape as [kiwoom-client](https://github.com/younghwan91/kiwoom-client) and [krx-news-client](https://github.com/younghwan91/krx-news-client).
- **Failures are distinguishable.** Quota exhaustion is an exception, a missing filing is `None`. Pass an `on_status` callback to the statement calls and you receive the raw DART status code (013 no filing, 010/800/900 real failure) without changing the return type.
- **A blocked path is documented as blocked.** The KRX scraper's silent empty list is not hidden; [docs/krx-blocked.md](docs/krx-blocked.md) traces it through the code.

## More

Statements for many tickers in one call (DART `fnlttMultiAcnt`, up to 100 tickers):

```python
financials = await dart.fetch_financials_batch(["005930", "000660", "035420"], year=2025)
for ticker, fs in financials.items():
    if fs is not None:
        print(ticker, fs.revenue, fs.net_income)
```

Rotating several DART keys: catch `DartQuotaExceededError` and move on.

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
    raise RuntimeError("all keys exhausted their daily quota")
```

Screening and ranking: filter and sort in place on the PER and PBR that `NaverScraper` fills (the KRX bulk path is blocked, so pass the tickers you want):

```python
from krx_fundamentals_client import NaverScraper, RankingMetric, rank_stocks, screen_stocks

naver = NaverScraper()
try:
    ratios = await naver.fetch_batch(["005930", "000660", "035420", "005380"])
    value_stocks = screen_stocks(ratios, per_max=15.0, pbr_max=1.2)
    top_by_pbr = rank_stocks(ratios, RankingMetric.PBR)
finally:
    await naver.close()
```

## Structure

Caller → scraper class → source, nothing in between. Every DART detail call needs a `corp_code`; the first call downloads the full mapping once and caches it on the instance for 24 hours, so reuse one scraper across tickers. Diagram and DART call order: [docs/architecture.md](docs/architecture.md) (Korean).

## Development

```bash
uv sync --extra dev
uv run pytest                        # tests (HTTP mocked with pytest-httpx)
uv run ruff check src/ tests/        # lint
```

## Docs

- [docs/architecture.md](docs/architecture.md) — scraper structure, ranking/screening, DART call order
- [docs/krx-blocked.md](docs/krx-blocked.md) — code walkthrough of the KRX block
- [`examples/`](examples/) — basic usage, screening, portfolio examples

(The docs under `docs/` are written in Korean.)

## License

Apache-2.0 ([LICENSE](LICENSE))

## Author

**Younghwan Chae** · [GitHub @younghwan91](https://github.com/younghwan91) · [LinkedIn](https://www.linkedin.com/in/younghwan-chae/)

## Contributing & Issues

- 🐛 Bugs & questions → [Issues](https://github.com/younghwan91/krx-fundamentals-client/issues)
- 📈 Updates → [Follow @younghwan91](https://github.com/younghwan91)


## Related projects — open-source quant stack

Part of an open-source stack spanning Korean equities, US equities and crypto. Each repository stands on its own.

| Market | Project | What it is |
|---|---|---|
| 🇰🇷 Korean equities | **[kiwoom-client](https://github.com/younghwan91/kiwoom-client)** | Kiwoom Securities REST API client — full domestic-equity endpoint coverage, real-time WebSocket, sync + async (`pip install kiwoom-client`) |
| 🇰🇷 Korean equities | **[krx-news-client](https://github.com/younghwan91/krx-news-client)** | Korean market news & disclosures as one schema — Python client library (DART + Toss Securities) |
| 🇰🇷 Korean equities | **[krx-quant-core](https://github.com/younghwan91/krx-quant-core)** | Shared Python core for Korean-equity quant systems — KRX tick, price-limit and session rules, date-aware transaction-tax cost model, Kiwoom order guards, DART material-disclosure risk classification, fill simulation, Deflated Sharpe and purged CV stats |
| 🇰🇷 Korean equities | **[fin-checkup](https://github.com/younghwan91/fin-checkup)** | Telegram alerts for risk disclosures + a DART/SEC financial health checkup — reports measurements and facts, never a recommendation |
| 🇰🇷 Korean equities | **[quant-airflow](https://github.com/younghwan91/quant-airflow)** | Airflow pipeline collecting Korean market data into TimescaleDB — delisted names included, so downstream backtests aren't survivorship-biased |
| 🇰🇷 Korean equities | **[swing-it](https://github.com/younghwan91/swing-it)** | KOSPI/KOSDAQ alpha validation framework — judged on the per-trade distribution, with random null controls, purged CV and Deflated Sharpe enforced as CI guardrails |
| 🇺🇸 US equities | **[portfolio-research](https://github.com/younghwan91/portfolio-research)** | US equity factor engine — walk-forward gated by Deflated Sharpe and PBO on point-in-time, survivorship-bias-free data; tactical ETF allocation goes through the same gate |
| 🇺🇸 US equities | **[macro-sector-agent](https://github.com/younghwan91/macro-sector-agent)** | Top-down US sector-cycle research — asks which industry has been forgotten, not what to buy; the machine excludes, never picks |
| 🇺🇸 US equities | **[automated-stock-trading-systems](https://github.com/younghwan91/automated-stock-trading-systems)** | Backtester for Bensdorp's seven non-correlated trading systems (educational reimplementation) |
| ₿ Crypto | **[binance-quant-engine](https://github.com/younghwan91/binance-quant-engine)** | Crypto futures backtest & execution engine — zero lookahead, backtest↔live parity |
| ₿ Crypto | **[crypto-quant-insights](https://github.com/younghwan91/crypto-quant-insights)** | Chart-backed research notes from validating a live futures system — crash stress tests, Kelly leverage, live/backtest execution gaps |

