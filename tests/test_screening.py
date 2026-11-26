from __future__ import annotations

import pytest

from krx_fundamentals_client.models.schemas import Company, InvestmentRatio, Market, RankingMetric
from krx_fundamentals_client.screening import rank_stocks, screen_stocks

_RATIOS = [
    InvestmentRatio(
        ticker="005930", name="삼성전자", market=Market.KOSPI,
        per=12.0, pbr=1.3, roe=15.0, market_cap=500000.0, dividend_yield=2.1,
    ),
    InvestmentRatio(
        ticker="000660", name="SK하이닉스", market=Market.KOSPI,
        per=20.0, pbr=2.0, roe=8.0, market_cap=100000.0, dividend_yield=0.5,
    ),
    InvestmentRatio(
        ticker="035420", name="NAVER", market=Market.KOSDAQ,
        per=None, pbr=3.0, roe=10.0, market_cap=50000.0, dividend_yield=None,
    ),
]

_COMPANIES = [
    Company(ticker="005930", name="삼성전자", sector="반도체"),
    Company(ticker="000660", name="SK하이닉스", sector="반도체"),
    Company(ticker="035420", name="NAVER", sector="IT서비스"),
]


def test_screen_stocks_no_filters_returns_all():
    assert screen_stocks(_RATIOS) == _RATIOS


def test_screen_stocks_by_market():
    result = screen_stocks(_RATIOS, market="kosdaq")
    assert [r.ticker for r in result] == ["035420"]


@pytest.mark.parametrize(
    "market", ["kospi", "KOSPI", "KoSpI", Market.KOSPI], ids=["lower", "upper", "mixed", "enum"]
)
def test_screen_stocks_by_market_accepts_case_and_enum(market):
    result = screen_stocks(_RATIOS, market=market)
    assert [r.ticker for r in result] == ["005930", "000660"]


def test_screen_stocks_rejects_unknown_market():
    with pytest.raises(ValueError, match="NASDAQ|nasdaq"):
        screen_stocks(_RATIOS, market="NASDAQ")


def test_screen_stocks_rejects_empty_market_string():
    with pytest.raises(ValueError):
        screen_stocks(_RATIOS, market="")


def test_screen_stocks_excludes_missing_market_only_when_filtering():
    unknown_market = InvestmentRatio(ticker="000001")
    ratios = [unknown_market, *_RATIOS]

    assert screen_stocks(ratios, market="kospi") == _RATIOS[:2]
    assert screen_stocks(ratios, market=None) == ratios


def test_screen_stocks_by_per_range_excludes_missing_values():
    result = screen_stocks(_RATIOS, per_min=10.0, per_max=15.0)
    assert [r.ticker for r in result] == ["005930"]


def test_screen_stocks_by_sector_requires_companies():
    result = screen_stocks(_RATIOS, sector="반도체", companies=_COMPANIES)
    assert {r.ticker for r in result} == {"005930", "000660"}


def test_screen_stocks_by_dividend_yield_min():
    result = screen_stocks(_RATIOS, dividend_yield_min=1.0)
    assert [r.ticker for r in result] == ["005930"]


def test_rank_stocks_descending_default():
    result = rank_stocks(_RATIOS, RankingMetric.MARKET_CAP)
    assert [r.ticker for r in result] == ["005930", "000660", "035420"]


def test_rank_stocks_ascending():
    result = rank_stocks(_RATIOS, RankingMetric.PER, ascending=True)
    assert [r.ticker for r in result] == ["005930", "000660"]


def test_rank_stocks_unknown_metric_falls_back_to_market_cap():
    result = rank_stocks(_RATIOS, RankingMetric.REVENUE)
    assert [r.ticker for r in result] == ["005930", "000660", "035420"]
