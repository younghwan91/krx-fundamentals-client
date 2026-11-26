"""CLI 비교표 렌더링과 종목명 해석 (네트워크 없음)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from krx_fundamentals_client import cli
from krx_fundamentals_client.models.schemas import InvestmentRatio, Market
from krx_fundamentals_client.scrapers.naver import NaverScraper


def _ratio(**kw) -> InvestmentRatio:
    base = dict(
        ticker="005930", name="삼성전자", market=Market.KOSPI, price=150.0,
        low_52w=100.0, high_52w=200.0, per=5.39, market_cap=10_026_368.0,
    )
    return InvestmentRatio(**{**base, **kw})


def test_display_width_counts_hangul_as_two():
    assert cli.display_width("PER") == 3
    assert cli.display_width("삼성전자") == 8


def test_krw_eok_formats_jo_and_eok():
    assert cli._krw_eok(10_026_368.0) == "1,002조 6,368억"
    assert cli._krw_eok(651.0) == "651억"
    assert cli._krw_eok(30_000.0) == "3조"
    assert cli._krw_eok(None) == "-"


def test_range_bar_position_and_missing():
    assert cli.range_bar(_ratio()) == "█████░░░░░  50%"
    assert cli.range_bar(_ratio(price=999.0)).endswith("100%")
    assert cli.range_bar(_ratio(high_52w=None)) == "-"
    assert cli.range_bar(_ratio(high_52w=100.0)) == "-"


def test_render_table_columns_line_up():
    table = cli.render_table([_ratio(), _ratio(ticker="000660", name="SK하이닉스", per=None)])
    lines = table.splitlines()
    assert "삼성전자" in lines[0] and "SK하이닉스" in lines[0]
    assert "005930" in lines[1] and "000660" in lines[1]
    per = next(line for line in lines if line.startswith("PER"))
    assert per.split()[1:] == ["5.39배", "-"]
    widths = {cli.display_width(line) for line in lines if line and not line.startswith("─")}
    assert len(widths) == 1  # 모든 행의 표시 폭이 같다 = 오른쪽 정렬이 맞다


async def test_resolve_ticker_passthrough_skips_search():
    naver = NaverScraper()
    naver.search = AsyncMock()
    assert await cli.resolve(naver, "005930") == "005930"
    naver.search.assert_not_called()


async def test_resolve_prefers_exact_name():
    naver = NaverScraper()
    naver.search = AsyncMock(return_value=[
        ("0162Z0", "RISE 삼성전자SK하이닉스채권혼합50", Market.KOSPI),
        ("005930", "삼성전자", Market.KOSPI),
    ])
    assert await cli.resolve(naver, "삼성전자") == "005930"
    naver.search.return_value = [("0162Z0", "RISE 삼성전자SK하이닉스채권혼합50", None)]
    assert await cli.resolve(naver, "삼성") == "0162Z0"
    naver.search.return_value = []
    assert await cli.resolve(naver, "없는종목") is None


async def test_naver_search_parses_and_drops_foreign():
    naver = NaverScraper()
    resp = MagicMock()
    resp.json.return_value = {"items": [
        {"code": "005930", "name": "삼성전자", "typeCode": "KOSPI", "nationCode": "KOR"},
        {"code": "AAPL", "name": "애플", "typeCode": "NASDAQ", "nationCode": "USA"},
    ]}
    naver.fetch = AsyncMock(return_value=resp)
    assert await naver.search("삼성") == [("005930", "삼성전자", Market.KOSPI)]
    naver.fetch.side_effect = RuntimeError("down")
    assert await naver.search("삼성") == []


@pytest.fixture
def fake_naver(monkeypatch):
    def install(ratios):
        inst = NaverScraper()
        inst.search = AsyncMock(return_value=[])
        inst.fetch_batch = AsyncMock(return_value=ratios)
        monkeypatch.setattr(cli, "NaverScraper", lambda: inst)
        return inst
    return install


def test_main_json_output(fake_naver, capsys):
    fake_naver([_ratio()])
    assert cli.main(["005930", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["ticker"] == "005930" and out[0]["per"] == 5.39


def test_main_fails_when_nothing_found(fake_naver, capsys):
    fake_naver([])
    assert cli.main(["없는종목"]) == 1
    assert "찾지 못했습니다" in capsys.readouterr().err


def test_readme_cli_command_matches_entry_points():
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    scripts = tomllib.loads((root / "pyproject.toml").read_text())["project"]["scripts"]
    # uvx <패키지명> 이 바로 돌도록 패키지명과 같은 스크립트도 둔다
    assert scripts["krx-fundamentals-client"] == scripts["krx-fundamentals"] == (
        "krx_fundamentals_client.cli:main"
    )
    for name in ("README.md", "README.en.md"):
        assert "krx-fundamentals 삼성전자" in (root / name).read_text(encoding="utf-8")


def test_sort_ratios_direction_and_missing_last():
    a = _ratio(ticker="A", per=9.0, dividend_yield=1.0)
    b = _ratio(ticker="B", per=None, dividend_yield=3.0)
    c = _ratio(ticker="C", per=4.0, dividend_yield=None)
    assert [r.ticker for r in cli.sort_ratios([a, b, c], "per")] == ["C", "A", "B"]
    assert [r.ticker for r in cli.sort_ratios([a, b, c], "dividend")] == ["B", "A", "C"]


def test_main_sort_flag(fake_naver, capsys):
    fake_naver([_ratio(ticker="000001", per=9.0), _ratio(ticker="000002", per=4.0)])
    assert cli.main(["000001", "000002", "--sort", "per", "--json"]) == 0
    assert [r["ticker"] for r in json.loads(capsys.readouterr().out)] == ["000002", "000001"]
