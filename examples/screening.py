"""krx-fundamentals-client 종목 스크리닝 예제.

KRX에서 전 종목 투자지표를 한 번에 받아와 가치주/배당주 스크리닝과
랭킹을 인메모리로 계산합니다. (KRX 수집 경로가 막혀 있으면 빈 리스트가
반환됩니다 — docs/krx-blocked.md 참고)

사용법:
    pip install krx-fundamentals-client
    python examples/screening.py
"""

from __future__ import annotations

from krx_fundamentals_client import (
    InvestmentRatio,
    KrxScraper,
    Market,
    RankingMetric,
    rank_stocks,
    screen_stocks,
)


def print_header(title: str) -> None:
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def print_table(headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    header_line = " | ".join(h.center(w) for h, w in zip(headers, widths))
    separator = "-+-".join("-" * w for w in widths)
    print(f"  {header_line}")
    print(f"  {separator}")
    for row in rows:
        cells = (
            str(v).rjust(w) if i > 0 else str(v).ljust(w)
            for i, (v, w) in enumerate(zip(row, widths))
        )
        print(f"  {' | '.join(cells)}")


def fmt(value: float | None, suffix: str = "", decimal: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:,.{decimal}f}{suffix}"


def display_ratios(title: str, ratios: list[InvestmentRatio], limit: int = 10) -> None:
    print_header(title)
    if not ratios:
        print("  결과 없음")
        return
    headers = ["종목명", "시가총액", "PER", "PBR", "배당률"]
    widths = [12, 10, 8, 8, 8]
    rows = [
        [
            r.name[:12] or r.ticker,
            fmt(r.market_cap, "억", 0),
            fmt(r.per),
            fmt(r.pbr),
            fmt(r.dividend_yield, "%"),
        ]
        for r in ratios[:limit]
    ]
    print_table(headers, rows, widths)


async def main() -> None:
    print("🇰🇷 krx-fundamentals-client - 종목 스크리닝 예제")

    krx = KrxScraper()
    try:
        ratios: list[InvestmentRatio] = []
        for market in (Market.KOSPI, Market.KOSDAQ):
            ratios.extend(await krx.fetch_investment_ratios(market))
    finally:
        await krx.close()

    if not ratios:
        print("\n⚠️ KRX에서 투자지표를 받아오지 못했습니다 (docs/krx-blocked.md 참고).")
        return

    value_stocks = screen_stocks(
        ratios, market="kospi", per_min=0.1, per_max=10, pbr_min=0.1, pbr_max=1.0,
    )
    display_ratios("💎 가치주 (PER 10 이하, PBR 1 이하)", value_stocks)

    dividend_stocks = screen_stocks(ratios, dividend_yield_min=4.0)
    display_ratios("💰 배당주 (배당수익률 4% 이상)", dividend_stocks)

    top_market_cap = rank_stocks(ratios, RankingMetric.MARKET_CAP)
    display_ratios("🏆 시가총액 상위", top_market_cap)

    top_roe = rank_stocks(ratios, RankingMetric.ROE)
    display_ratios("📈 ROE 상위", top_roe)

    print(f"\n{'=' * 72}")
    print(f"  ✅ 스크리닝 완료! (전체 {len(ratios)}종목 중 계산)")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
