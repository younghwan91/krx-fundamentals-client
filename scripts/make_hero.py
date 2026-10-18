"""README 히어로 이미지 — 한 종목의 펀더멘탈이 라이브러리 몇 줄로 정규화되어 나오는 모습.

실행 (레포 루트):
    set -a; . ~/git/quant-airflow/.env; set +a     # DART_API_KEY (값은 출력하지 않는다)
    uv run --with matplotlib --with numpy python scripts/make_hero.py            # 실조회 → hero-data.json 저장 후 그림
    uv run --with matplotlib --with numpy python scripts/make_hero.py --from-json  # 저장된 JSON 으로 그림만 재생성

출력: docs/images/hero-light.png, docs/images/hero-dark.png, docs/images/hero-data.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from hero_style import caption, render_both  # noqa: E402

TICKER = "005930"
NAME_EN = "Samsung Electronics"
YEARS = list(range(2018, 2026))
DATA_PATH = ROOT / "docs/images/hero-data.json"


async def fetch() -> dict:
    from krx_fundamentals_client import DartScraper, NaverScraper

    api_key = os.environ.get("DART_API_KEY", "")
    if not api_key:
        sys.exit("DART_API_KEY 가 환경에 없다 — `set -a; . ~/git/quant-airflow/.env; set +a` 후 실행")

    dart, naver = DartScraper(api_key=api_key), NaverScraper()
    try:
        company = await dart.fetch_company(TICKER)
        statements = []
        for y in YEARS:
            s = await dart.fetch_financials(TICKER, y)
            if s is None:
                continue
            statements.append({
                k: getattr(s, k) for k in (
                    "year", "revenue", "operating_income", "net_income",
                    "total_assets", "total_liabilities", "total_equity",
                    "revenue_yoy", "operating_income_yoy", "net_income_yoy",
                )
            })
        latest_fy = statements[-1]["year"] if statements else YEARS[-1]
        div = await dart.fetch_dividends(TICKER, latest_fy)
        shares = await dart.fetch_shares_outstanding(TICKER, latest_fy)
        ratio = await naver.fetch_stock_info(TICKER)
    finally:
        await dart.close()
        await naver.close()

    out = {
        "ticker": TICKER,
        "name_en": NAME_EN,
        "name_en_dart": (company.name_en if company else None),
        "fetched": date.today().isoformat(),
        "statements": statements,
        "shares": (
            {k: getattr(shares, k) for k in ("year", "shares_outstanding", "stlm_dt")}
            if shares else None
        ),
        "dividend": (
            {k: getattr(div, k) for k in ("year", "dividend_per_share", "payout_ratio", "dividend_yield")}
            if div else None
        ),
        "ratio": (
            {k: getattr(ratio, k) for k in ("market_cap", "per", "pbr", "eps", "bps", "dividend_yield", "price", "foreign_ratio")}
            if ratio else None
        ),
    }
    return out


def _fmt_trn(v: float | None) -> str:
    return "–" if v is None else f"{v / 1e12:,.1f}T"


def _fmt(v: float | None, fmt: str, unit: str = "") -> str:
    return "–" if v is None else f"{format(v, fmt)}{unit}"


def draw_factory(d: dict):
    def draw(fig, ax, p):
        fig.delaxes(ax)
        gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.07, left=0.06, right=0.99, top=0.75, bottom=0.10)
        ax = fig.add_subplot(gs[0, 0])
        tiles_gs = gs[0, 1].subgridspec(3, 2, wspace=0.10, hspace=0.22)

        fig.suptitle(
            "One company, one schema: fundamentals from DART and Naver, normalized in a few lines",
            x=0.0, y=0.985, ha="left", fontsize=16, fontweight="bold", color=p["ink"],
        )
        fig.text(
            0.0, 0.91,
            f"{d['name_en']} ({d['ticker']})  ·  DartScraper.fetch_financials / fetch_dividends  +  NaverScraper.fetch_stock_info  →  Pydantic models",
            color=p["ink2"], fontsize=11, ha="left", va="top",
        )

        # --- left: revenue vs operating income (same unit, one axis) ---
        st = d["statements"]
        yrs = [s["year"] for s in st]
        rev = [(s["revenue"] or 0) / 1e12 for s in st]
        opi = [(s["operating_income"] or 0) / 1e12 for s in st]
        x = list(range(len(yrs)))
        w = 0.32
        ax.bar([i - w / 2 - 0.02 for i in x], rev, width=w, color=p["blue"], label="Revenue", zorder=3)
        ax.bar([i + w / 2 + 0.02 for i in x], opi, width=w, color=p["amber"], label="Operating income", zorder=3)
        ax.set_xticks(x, [f"FY{y}" for y in yrs])
        ax.set_ylabel("KRW trillion (consolidated, annual)")
        ax.set_ylim(0, max(rev) * 1.18)
        ax.yaxis.set_major_formatter(lambda v, _: f"{v:,.0f}")
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", length=0)
        ax.spines["left"].set_visible(False)
        ax.legend(loc="upper left", ncol=2, handlelength=1.0, handleheight=1.0, borderaxespad=0)
        i = x[-1]
        ax.annotate(f"{rev[-1]:,.1f}T", (i - w / 2 - 0.02, rev[-1]), xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10.5, color=p["ink"], fontweight="bold")
        ax.annotate(f"{opi[-1]:,.1f}T", (i + w / 2 + 0.02, opi[-1]), xytext=(0, 4), textcoords="offset points",
                    ha="center", va="bottom", fontsize=10.5, color=p["ink"], fontweight="bold")
        ax.set_title("FinancialStatement.revenue / .operating_income", fontsize=12, color=p["ink"], pad=8)

        # --- right: stat tiles (값이 있는 것부터 6개) ---
        r = d.get("ratio") or {}
        dv = d.get("dividend") or {}
        sh = d.get("shares") or {}
        last = st[-1]
        fy = last["year"]
        op_margin = (
            last["operating_income"] / last["revenue"] * 100
            if last.get("operating_income") is not None and last.get("revenue") else None
        )
        candidates = [
            ("PER", r.get("per"), _fmt(r.get("per"), ".1f", "x"), "InvestmentRatio.per"),
            ("PBR", r.get("pbr"), _fmt(r.get("pbr"), ".2f", "x"), "InvestmentRatio.pbr"),
            ("Dividend yield", r.get("dividend_yield"), _fmt(r.get("dividend_yield"), ".2f", "%"), "InvestmentRatio.dividend_yield"),
            (f"DPS FY{dv.get('year')}", dv.get("dividend_per_share"), _fmt(dv.get("dividend_per_share"), ",.0f", " KRW"), "Dividend.dividend_per_share"),
            (f"Net income FY{fy}", last.get("net_income"), _fmt_trn(last.get("net_income")), "FinancialStatement.net_income"),
            (f"Operating margin FY{fy}", op_margin, _fmt(op_margin, ".1f", "%"), "operating_income / revenue"),
            (f"Revenue YoY FY{fy}", last.get("revenue_yoy"), _fmt(last.get("revenue_yoy"), "+.1f", "%"), "FinancialStatement.revenue_yoy"),
            (f"Total equity FY{fy}", last.get("total_equity"), _fmt_trn(last.get("total_equity")), "FinancialStatement.total_equity"),
            ("Shares outstanding", sh.get("shares_outstanding"), "–" if sh.get("shares_outstanding") is None else f"{sh['shares_outstanding'] / 1e9:,.2f}B", "SharesOutstanding.shares_outstanding"),
            ("Last price", r.get("price"), _fmt(r.get("price"), ",.0f", " KRW"), "InvestmentRatio.price"),
            ("Market cap", r.get("market_cap"), "–" if r.get("market_cap") is None else f"{r['market_cap'] / 1e4:,.0f}T", "InvestmentRatio.market_cap"),
            ("EPS", r.get("eps"), _fmt(r.get("eps"), ",.0f", " KRW"), "InvestmentRatio.eps"),
        ]
        tiles = [(lab, val, fld) for lab, v, val, fld in candidates if v is not None][:6]
        for k, (label, value, field) in enumerate(tiles):
            t = fig.add_subplot(tiles_gs[k // 2, k % 2])
            t.set_axis_off()
            t.add_patch(__import__("matplotlib").patches.FancyBboxPatch(
                (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.06", transform=t.transAxes,
                facecolor=p["surface2"], edgecolor=p["grid"], linewidth=1, zorder=0, mutation_aspect=1.6,
            ))
            t.text(0.08, 0.80, label, color=p["ink2"], fontsize=10.5, ha="left", va="center", transform=t.transAxes)
            t.text(0.08, 0.47, value, color=p["ink"], fontsize=19, fontweight="bold", ha="left", va="center", transform=t.transAxes)
            t.text(0.08, 0.16, field, color=p["ink3"], fontsize=7.2 if len(field) <= 32 else 6.3, ha="left", va="center", transform=t.transAxes, family="monospace")

        caption(
            fig,
            f"Source: DART Open API (fnlttSinglAcnt consolidated annual, alotMatter) and Naver Finance mobile API, "
            f"fetched {d['fetched']}. Public filings; figures as reported.",
            p,
        )

    return draw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", action="store_true", help="hero-data.json 을 읽어 그림만 다시 만든다")
    args = ap.parse_args()

    if args.from_json:
        d = json.loads(DATA_PATH.read_text())
    else:
        d = asyncio.run(fetch())
        DATA_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        print(f"saved {DATA_PATH.relative_to(ROOT)}: {len(d['statements'])} statements, dividend={'ok' if d['dividend'] else 'none'}, ratio={'ok' if d['ratio'] else 'none'}")

    paths = render_both(draw_factory(d), out_dir=str(ROOT / "docs/images"), name="hero", figsize=(12, 5))
    for pth in paths:
        print("wrote", Path(pth).relative_to(ROOT))


if __name__ == "__main__":
    main()
