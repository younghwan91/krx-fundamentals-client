"""krx-fundamentals-client 포트폴리오 분석 예제.

여러 종목의 투자지표(네이버)와 배당 이력(DART)을 비동기 병렬로 수집해
요약 테이블과 포트폴리오 평균을 출력합니다.

사용법:
    pip install krx-fundamentals-client
    export DART_API_KEY=...   # https://opendart.fss.or.kr 에서 무료 발급
    python examples/portfolio_analysis.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from datetime import datetime

from krx_fundamentals_client import DartScraper, Dividend, InvestmentRatio, NaverScraper

PORTFOLIO: list[tuple[str, str]] = [
    ("005930", "삼성전자"),
    ("000660", "SK하이닉스"),
    ("035420", "NAVER"),
    ("035720", "카카오"),
    ("005380", "현대차"),
]


@dataclass
class StockData:
    ticker: str
    name: str
    ratio: InvestmentRatio | None = None
    dividend: Dividend | None = None


def print_header(title: str) -> None:
    print(f"\n{'=' * 76}")
    print(f"  {title}")
    print(f"{'=' * 76}")


def print_table(headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    header_line = " | ".join(h.center(w) for h, w in zip(headers, widths))
    separator = "-+-".join("-" * w for w in widths)
    print(f"  {header_line}")
    print(f"  {separator}")
    for row in rows:
        line = " | ".join(
            str(v).rjust(w) if i > 0 else str(v).ljust(w)
            for i, (v, w) in enumerate(zip(row, widths))
        )
        print(f"  {line}")


def fmt(value: float | None, suffix: str = "", decimal: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:,.{decimal}f}{suffix}"


async def fetch_stock_data(
    naver: NaverScraper, dart: DartScraper, ticker: str, name: str, year: int,
) -> StockData:
    ratio, dividend = await asyncio.gather(
        naver.fetch_stock_info(ticker),
        dart.fetch_dividends(ticker, year),
    )
    return StockData(ticker=ticker, name=name, ratio=ratio, dividend=dividend)


def display_ratio_table(stocks: list[StockData]) -> None:
    print_header("📊 포트폴리오 투자 지표")
    headers = ["종목명", "현재가", "시가총액", "PER", "PBR", "배당률", "외국인"]
    widths = [10, 10, 10, 8, 8, 8, 8]
    rows = []
    for s in stocks:
        r = s.ratio
        rows.append([
            s.name[:10],
            fmt(r.price if r else None, "원", 0),
            fmt(r.market_cap if r else None, "억", 0),
            fmt(r.per if r else None),
            fmt(r.pbr if r else None),
            fmt(r.dividend_yield if r else None, "%"),
            fmt(r.foreign_ratio if r else None, "%"),
        ])
    print_table(headers, rows, widths)


def display_dividend_history(stocks: list[StockData]) -> None:
    print_header("💰 배당 정보")
    for s in stocks:
        if s.dividend is None:
            print(f"\n  {s.name} ({s.ticker}): 배당 데이터 없음")
            continue
        d = s.dividend
        dps = fmt(d.dividend_per_share, "원", 0)
        dy = fmt(d.dividend_yield, "%")
        pr = fmt(d.payout_ratio, "%")
        print(f"\n  {s.name} ({s.ticker}): {d.year}년 — 주당 {dps} | 수익률 {dy} | 배당성향 {pr}")


def display_portfolio_averages(stocks: list[StockData]) -> None:
    print_header("📋 포트폴리오 평균")
    metrics = [("PER", "per", "배"), ("PBR", "pbr", "배"), ("배당수익률", "dividend_yield", "%")]
    for label, attr, unit in metrics:
        values = [
            getattr(s.ratio, attr) for s in stocks if s.ratio and getattr(s.ratio, attr) is not None
        ]
        avg = sum(values) / len(values) if values else None
        print(f"  {label:>10}: {fmt(avg, unit)}")

    caps = [s.ratio.market_cap for s in stocks if s.ratio and s.ratio.market_cap is not None]
    if caps:
        print(f"\n  총 시가총액: {sum(caps):,.0f}억원")


async def main() -> None:
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        print("❌ DART_API_KEY 환경변수를 설정하세요 (https://opendart.fss.or.kr)")
        sys.exit(1)

    year = datetime.now().year - 1
    naver = NaverScraper()
    dart = DartScraper(api_key=api_key)

    print("🇰🇷 krx-fundamentals-client - 포트폴리오 분석 예제")
    print(f"   종목: {', '.join(name for _, name in PORTFOLIO)}")

    try:
        stocks = await asyncio.gather(
            *(fetch_stock_data(naver, dart, ticker, name, year) for ticker, name in PORTFOLIO)
        )
        stocks = list(stocks)

        display_ratio_table(stocks)
        display_dividend_history(stocks)
        display_portfolio_averages(stocks)
    finally:
        await naver.close()
        await dart.close()

    print(f"\n{'=' * 76}")
    print("  ✅ 포트폴리오 분석 완료!")
    print(f"{'=' * 76}")


if __name__ == "__main__":
    asyncio.run(main())
