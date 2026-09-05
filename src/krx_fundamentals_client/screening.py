from __future__ import annotations

from krx_fundamentals_client.models.schemas import Company, InvestmentRatio, RankingMetric

# InvestmentRatio에 없는 지표(revenue, net_income)는 market_cap으로 대체한다 —
# 기존 서비스 계층(services/cache.py)의 동작을 그대로 보존한 것.
_RANKING_ATTR = {
    RankingMetric.MARKET_CAP: "market_cap",
    RankingMetric.PER: "per",
    RankingMetric.PBR: "pbr",
    RankingMetric.ROE: "roe",
    RankingMetric.DIVIDEND_YIELD: "dividend_yield",
}


def screen_stocks(
    ratios: list[InvestmentRatio],
    *,
    companies: list[Company] | None = None,
    market: str | None = None,
    sector: str | None = None,
    per_min: float | None = None,
    per_max: float | None = None,
    pbr_min: float | None = None,
    pbr_max: float | None = None,
    roe_min: float | None = None,
    roe_max: float | None = None,
    dividend_yield_min: float | None = None,
    market_cap_min: float | None = None,
) -> list[InvestmentRatio]:
    """주어진 투자지표 목록을 조건으로 필터링한다.

    `sector` 필터를 쓰려면 `companies`(섹터 정보를 담은 Company 목록)를 함께 넘겨야 한다.
    """
    filtered = []
    for r in ratios:
        if market and r.market and r.market.value != market:
            continue
        if per_min is not None and (r.per is None or r.per < per_min):
            continue
        if per_max is not None and (r.per is None or r.per > per_max):
            continue
        if pbr_min is not None and (r.pbr is None or r.pbr < pbr_min):
            continue
        if pbr_max is not None and (r.pbr is None or r.pbr > pbr_max):
            continue
        if roe_min is not None and (r.roe is None or r.roe < roe_min):
            continue
        if roe_max is not None and (r.roe is None or r.roe > roe_max):
            continue
        if dividend_yield_min is not None and (
            r.dividend_yield is None or r.dividend_yield < dividend_yield_min
        ):
            continue
        if market_cap_min is not None and (
            r.market_cap is None or r.market_cap < market_cap_min
        ):
            continue
        filtered.append(r)

    if sector:
        sector_tickers = {
            c.ticker for c in (companies or []) if sector.lower() in c.sector.lower()
        }
        filtered = [r for r in filtered if r.ticker in sector_tickers]

    return filtered


def rank_stocks(
    ratios: list[InvestmentRatio],
    metric: RankingMetric,
    *,
    ascending: bool = False,
) -> list[InvestmentRatio]:
    """주어진 투자지표 목록을 지정한 지표 기준으로 정렬한다 (값이 없는 종목은 제외)."""
    attr = _RANKING_ATTR.get(metric, "market_cap")
    valid = [r for r in ratios if getattr(r, attr, None) is not None]
    valid.sort(key=lambda r: getattr(r, attr, 0) or 0, reverse=not ascending)
    return valid
