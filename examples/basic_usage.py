"""krx-fundamentals-client 기본 사용 예제.

DART/네이버 스크레이퍼를 직접 호출해 한 종목의 기업 개황, 재무제표,
투자지표, 배당, 대주주, 임원 정보를 순서대로 조회합니다.

사용법:
    pip install krx-fundamentals-client
    export DART_API_KEY=...   # https://opendart.fss.or.kr 에서 무료 발급
    python examples/basic_usage.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime

from krx_fundamentals_client import DartScraper, NaverScraper

TICKER = "005930"  # 삼성전자


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def show_company(dart: DartScraper, ticker: str) -> None:
    print_header(f"기업 개황 ({ticker})")
    company = await dart.fetch_company(ticker)
    if company is None:
        print("  데이터 없음")
        return
    fields = [
        ("기업명", company.name),
        ("영문명", company.name_en),
        ("시장", company.market),
        ("대표이사", company.ceo),
        ("홈페이지", company.website),
        ("결산월", f"{company.fiscal_month}월"),
    ]
    for label, value in fields:
        if value:
            print(f"  {label}: {value}")


async def show_financials(dart: DartScraper, ticker: str, year: int) -> None:
    print_header(f"재무제표 ({ticker}, {year})")
    stmt = await dart.fetch_financials(ticker, year)
    if stmt is None:
        print("  데이터 없음")
        return
    if stmt.revenue is not None:
        print(f"  매출액:     {stmt.revenue:>15,.0f}")
    if stmt.operating_income is not None:
        print(f"  영업이익:   {stmt.operating_income:>15,.0f}")
    if stmt.net_income is not None:
        print(f"  당기순이익: {stmt.net_income:>15,.0f}")


async def show_ratios(naver: NaverScraper, ticker: str) -> None:
    print_header(f"투자 지표 ({ticker})")
    ratio = await naver.fetch_stock_info(ticker)
    if ratio is None:
        print("  데이터 없음")
        return
    metrics = [
        ("종목명", ratio.name, ""),
        ("현재가", ratio.price, "원"),
        ("시가총액", ratio.market_cap, "억원"),
        ("PER", ratio.per, "배"),
        ("PBR", ratio.pbr, "배"),
        ("EPS", ratio.eps, "원"),
        ("BPS", ratio.bps, "원"),
        ("배당수익률", ratio.dividend_yield, "%"),
    ]
    for label, value, unit in metrics:
        if value is not None:
            print(f"  {label:>10}: {value} {unit}")


async def show_dividends(dart: DartScraper, ticker: str, year: int) -> None:
    print_header(f"배당 정보 ({ticker}, {year})")
    div = await dart.fetch_dividends(ticker, year)
    if div is None:
        print("  데이터 없음")
        return
    if div.dividend_per_share is not None:
        print(f"  주당배당금: {div.dividend_per_share:>10,.0f}원")
    if div.dividend_yield is not None:
        print(f"  배당수익률: {div.dividend_yield:>10.2f}%")


async def show_shareholders(dart: DartScraper, ticker: str, year: int) -> None:
    print_header(f"대주주 현황 ({ticker}, {year})")
    shareholders = await dart.fetch_shareholders(ticker, year)
    if not shareholders:
        print("  데이터 없음")
        return
    for sh in shareholders[:5]:
        print(f"    {sh.name:>12} | {sh.shares:>15,}주 | {sh.ownership_pct:>6.2f}%")


async def main() -> None:
    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        print("❌ DART_API_KEY 환경변수를 설정하세요 (https://opendart.fss.or.kr)")
        sys.exit(1)

    year = datetime.now().year - 1  # 최신 확정 사업연도
    dart = DartScraper(api_key=api_key)
    naver = NaverScraper()

    print("🇰🇷 krx-fundamentals-client - 기본 사용 예제")
    try:
        await show_company(dart, TICKER)
        await show_financials(dart, TICKER, year)
        await show_ratios(naver, TICKER)
        await show_dividends(dart, TICKER, year)
        await show_shareholders(dart, TICKER, year)
    finally:
        await dart.close()
        await naver.close()

    print(f"\n{'=' * 60}")
    print("  ✅ 완료!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
