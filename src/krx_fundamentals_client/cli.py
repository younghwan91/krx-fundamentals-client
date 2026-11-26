"""터미널에서 종목 몇 개의 투자지표를 나란히 본다 — API 키 없이 네이버만 쓴다.

    uvx krx-fundamentals-client 삼성전자 SK하이닉스 005380
    krx-fundamentals 삼성전자 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence

from krx_fundamentals_client.models.schemas import InvestmentRatio
from krx_fundamentals_client.scrapers.naver import NaverScraper

_TICKER = re.compile(r"^[0-9A-Z]{6}$")
_BAR_WIDTH = 10


def display_width(text: str) -> int:
    """한글처럼 두 칸을 차지하는 글자를 2로 센 터미널 표시 폭."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in text)


def _pad(text: str, width: int, right: bool) -> str:
    gap = " " * max(width - display_width(text), 0)
    return gap + text if right else text + gap


def _num(value: float | None, suffix: str = "", decimal: int = 2) -> str:
    return "-" if value is None else f"{value:,.{decimal}f}{suffix}"


def _krw_eok(value: float | None) -> str:
    """억원 단위 값을 "1,268조 6,425억" 꼴로."""
    if value is None:
        return "-"
    jo, eok = divmod(round(value), 10_000)
    if jo and eok:
        return f"{jo:,}조 {eok:,}억"
    return f"{jo:,}조" if jo else f"{eok:,}억"


def range_bar(r: InvestmentRatio) -> str:
    """52주 최저~최고 사이에서 현재가가 어디쯤인지 막대와 %로."""
    if r.price is None or r.low_52w is None or r.high_52w is None or r.high_52w <= r.low_52w:
        return "-"
    pos = min(max((r.price - r.low_52w) / (r.high_52w - r.low_52w), 0.0), 1.0)
    filled = round(pos * _BAR_WIDTH)
    return "█" * filled + "░" * (_BAR_WIDTH - filled) + f" {pos * 100:3.0f}%"


ROWS: list[tuple[str, Callable[[InvestmentRatio], str]]] = [
    ("시장", lambda r: r.market.value.upper() if r.market else "-"),
    ("현재가", lambda r: _num(r.price, "원", 0)),
    ("시가총액", lambda r: _krw_eok(r.market_cap)),
    ("PER", lambda r: _num(r.per, "배")),
    ("PBR", lambda r: _num(r.pbr, "배")),
    ("EPS", lambda r: _num(r.eps, "원", 0)),
    ("BPS", lambda r: _num(r.bps, "원", 0)),
    ("배당수익률", lambda r: _num(r.dividend_yield, "%")),
    ("외국인소진율", lambda r: _num(r.foreign_ratio, "%")),
    ("52주 위치", range_bar),
]


def render_table(ratios: Sequence[InvestmentRatio]) -> str:
    """종목을 열로, 지표를 행으로 둔 비교표 문자열."""
    header = [""] + [r.name or r.ticker for r in ratios]
    sub = [""] + [r.ticker for r in ratios]
    body = [[label] + [fmt(r) for r in ratios] for label, fmt in ROWS]
    grid = [header, sub, *body]
    widths = [max(display_width(row[c]) for row in grid) for c in range(len(header))]

    def line(row: list[str]) -> str:
        cells = [_pad(row[0], widths[0], right=False)]
        cells += [_pad(v, w, right=True) for v, w in zip(row[1:], widths[1:])]
        return "  ".join(cells).rstrip()

    rule = "─" * (sum(widths) + 2 * (len(widths) - 1))
    return "\n".join([line(header), line(sub), rule, *(line(row) for row in body)])


# --sort 값 → (InvestmentRatio 필드, 내림차순 여부). 싼 것(PER·PBR)은 오름차순, 큰 것은 내림차순.
SORT_KEYS: dict[str, tuple[str, bool]] = {
    "per": ("per", False),
    "pbr": ("pbr", False),
    "dividend": ("dividend_yield", True),
    "cap": ("market_cap", True),
}


def sort_ratios(ratios: Sequence[InvestmentRatio], key: str) -> list[InvestmentRatio]:
    """지정 지표로 정렬한다. 값이 없는 종목은 버리지 않고 맨 뒤에 둔다."""
    attr, desc = SORT_KEYS[key]
    known = [r for r in ratios if getattr(r, attr) is not None]
    known.sort(key=lambda r: getattr(r, attr), reverse=desc)
    return known + [r for r in ratios if getattr(r, attr) is None]


async def resolve(naver: NaverScraper, query: str) -> str | None:
    """6자리 종목코드는 그대로, 아니면 종목명을 검색해 이름이 정확히 같은 것(없으면 첫 결과)."""
    if _TICKER.match(query.upper()):
        return query.upper()
    hits = await naver.search(query)
    if not hits:
        return None
    exact = [code for code, name, _ in hits if name.replace(" ", "") == query.replace(" ", "")]
    return exact[0] if exact else hits[0][0]


async def run(queries: Sequence[str], as_json: bool, sort: str | None = None) -> int:
    naver = NaverScraper()
    naver.min_delay, naver.max_delay = 0.1, 0.3  # 몇 종목뿐이라 짧게
    try:
        tickers: list[str] = []
        for q in queries:
            code = await resolve(naver, q)
            if code is None:
                print(f"'{q}' 에 맞는 종목을 찾지 못했습니다.", file=sys.stderr)
            elif code not in tickers:
                tickers.append(code)
        ratios = await naver.fetch_batch(tickers) if tickers else []
    finally:
        await naver.close()

    missing = set(tickers) - {r.ticker for r in ratios}
    for code in sorted(missing):
        print(f"{code}: 네이버에서 투자지표를 받지 못했습니다.", file=sys.stderr)
    if not ratios:
        return 1
    if sort:
        ratios = sort_ratios(ratios, sort)
    if as_json:
        print(json.dumps([r.model_dump(mode="json") for r in ratios], ensure_ascii=False, indent=2))
    else:
        print(render_table(ratios))
        print("\n출처: 네이버 증권 · 투자 판단의 근거가 아닌 참고용 수치입니다.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="krx-fundamentals",
        description=(
            "국내 종목 투자지표(PER·PBR·EPS·배당수익률·52주 위치)를 나란히 봅니다. "
            "API 키가 필요 없습니다."
        ),
        epilog="예: krx-fundamentals 삼성전자 SK하이닉스 005380",
    )
    parser.add_argument("stocks", nargs="+", metavar="종목", help="종목명 또는 6자리 종목코드")
    parser.add_argument("--json", action="store_true", help="표 대신 InvestmentRatio JSON 으로")
    parser.add_argument(
        "--sort",
        choices=sorted(SORT_KEYS),
        help="열 순서: per·pbr 은 낮은 순, dividend(배당수익률)·cap(시가총액)은 높은 순",
    )
    args = parser.parse_args(argv)
    return asyncio.run(run(args.stocks, args.json, args.sort))


if __name__ == "__main__":
    sys.exit(main())
