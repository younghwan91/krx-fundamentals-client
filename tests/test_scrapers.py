from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from krx_fundamentals_client.models.schemas import Market, ReportType
from krx_fundamentals_client.scrapers.base import BaseScraper
from krx_fundamentals_client.scrapers.dart import DartQuotaExceededError, DartScraper
from krx_fundamentals_client.scrapers.krx import KrxScraper
from krx_fundamentals_client.scrapers.naver import (
    NaverConsensusScraper,
    NaverScraper,
    parse_consensus,
    parse_estimate,
    parse_krw_eok,
    parse_unit_number,
)


async def test_dart_scraper_init():
    scraper = DartScraper(api_key="test_key")
    assert scraper.source == "dart"
    assert scraper.base_url == "https://opendart.fss.or.kr/api"
    assert scraper._corp_map == {}
    assert scraper._client is None


async def test_dart_check_api_key_empty():
    scraper = DartScraper(api_key="")
    assert scraper._check_api_key() is False


async def test_dart_check_api_key_set():
    scraper = DartScraper(api_key="test_key_12345")
    assert scraper._check_api_key() is True


async def test_dart_fetch_company_no_api_key():
    scraper = DartScraper(api_key="")
    result = await scraper.fetch_company("005930")
    assert result is None


async def test_dart_fetch_company_with_mock():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "corp_name": "삼성전자",
        "corp_name_eng": "Samsung Electronics",
        "corp_cls": "Y",
        "ceo_nm": "한종희",
        "adres": "경기도 수원시",
        "hm_url": "www.samsung.com",
        "ir_url": "https://www.samsung.com/ir",
        "est_dt": "19690113",
        "acc_mt": "12",
    }

    scraper.fetch = AsyncMock(return_value=mock_resp)
    company = await scraper.fetch_company("005930")

    assert company is not None
    assert company.ticker == "005930"
    assert company.name == "삼성전자"
    assert company.market == Market.KOSPI
    assert company.ceo == "한종희"
    assert company.fiscal_month == 12


async def test_dart_fetch_company_raises_on_quota_exhausted():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "020", "message": "요청 제한 초과"}
    scraper.fetch = AsyncMock(return_value=mock_resp)

    with pytest.raises(DartQuotaExceededError):
        await scraper.fetch_company("005930")


async def test_dart_fetch_financials_batch_splits_by_corp_code():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380", "000660": "00164779"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "매출액", "thstrm_amount": "300,000,000",
            },
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "당기순이익", "thstrm_amount": "20,000,000",
            },
            {
                "corp_code": "00164779", "fs_div": "CFS",
                "account_nm": "분기순이익", "thstrm_amount": "5,000,000",
            },
        ],
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_financials_batch(["005930", "000660"], year=2025)

    assert result["005930"] is not None
    assert result["005930"].revenue == 300_000_000
    assert result["005930"].net_income == 20_000_000
    assert result["000660"] is not None
    assert result["000660"].net_income == 5_000_000


async def test_dart_fetch_financials_batch_fills_prior_and_yoy():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "매출액",
                "thstrm_amount": "300,000,000", "frmtrm_amount": "200,000,000",
            },
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "당기순이익",
                "thstrm_amount": "10,000,000", "frmtrm_amount": "-20,000,000",
            },
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "자산총계",
                "thstrm_amount": "1,000,000,000", "frmtrm_amount": "900,000,000",
            },
        ],
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_financials_batch(["005930"], year=2025)

    fs = result["005930"]
    assert fs is not None
    assert fs.revenue_prior == 200_000_000
    assert fs.revenue_yoy == pytest.approx(50.0)
    assert fs.net_income_prior == -20_000_000
    assert fs.net_income_yoy == pytest.approx((10_000_000 - -20_000_000) / 20_000_000 * 100)
    # 대차대조표 항목은 전년동기/YoY 대상이 아니다.
    assert fs.total_assets == 1_000_000_000


async def test_dart_fetch_financials_batch_none_for_missing_corp():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380", "000660": "00164779"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "당기순이익", "thstrm_amount": "20,000,000",
            },
        ],
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_financials_batch(["005930", "000660"], year=2025)

    assert result["005930"] is not None
    assert result["000660"] is None


async def test_dart_fetch_financials_batch_raises_on_quota_exhausted():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "020", "message": "요청 제한 초과"}
    scraper.fetch = AsyncMock(return_value=mock_resp)

    with pytest.raises(DartQuotaExceededError):
        await scraper.fetch_financials_batch(["005930"], year=2025)


async def test_dart_fetch_financials_batch_chunks_over_100_tickers():
    scraper = DartScraper(api_key="test_key")
    tickers = [f"{i:06d}" for i in range(150)]
    scraper._corp_map = {t: f"corp{i}" for i, t in enumerate(tickers)}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "013"}  # 조회된 데이터 없음
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_financials_batch(tickers, year=2025)

    assert scraper.fetch.call_count == 2  # 150개 → 100 + 50
    assert len(result) == 150
    assert all(v is None for v in result.values())


async def test_dart_fetch_financials_batch_on_status_called_for_non_success():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "013", "message": "조회된 데이터가 없습니다"}
    scraper.fetch = AsyncMock(return_value=mock_resp)

    seen: list[tuple[str, str]] = []
    result = await scraper.fetch_financials_batch(
        ["005930"], year=2025, on_status=lambda status, context: seen.append((status, context)),
    )

    assert result["005930"] is None
    assert seen == [("013", "financials_batch(2025,annual)")]


async def test_dart_fetch_financials_batch_on_status_not_called_on_success():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "corp_code": "00126380", "fs_div": "CFS",
                "account_nm": "매출액", "thstrm_amount": "1,000",
            },
        ],
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    seen: list[tuple[str, str]] = []
    await scraper.fetch_financials_batch(
        ["005930"], year=2025, on_status=lambda status, context: seen.append((status, context)),
    )

    assert seen == []


async def test_dart_fetch_shares_outstanding_picks_common_stock_row():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "se": "보통주", "istc_totqy": "5,969,782,550",
                "stlm_dt": "20251231", "rcept_no": "20260310002061",
            },
            {
                "se": "합계", "istc_totqy": "5,979,782,550",
                "stlm_dt": "20251231", "rcept_no": "20260310002061",
            },
        ],
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_shares_outstanding("005930", year=2025)

    assert result is not None
    assert result.shares_outstanding == 5_969_782_550
    assert result.report_type == ReportType.ANNUAL
    assert result.stlm_dt == "20251231"
    assert result.knowledge_date == "20260310"
    assert scraper.fetch.call_count == 1


async def test_dart_fetch_shares_outstanding_falls_back_through_reports():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    empty_resp = MagicMock()
    empty_resp.json.return_value = {"status": "013"}
    q3_resp = MagicMock()
    q3_resp.json.return_value = {
        "status": "000",
        "list": [
            {
                "se": "보통주", "istc_totqy": "1,000,000",
                "stlm_dt": "20250930", "rcept_no": "20251110001234",
            },
        ],
    }
    scraper.fetch = AsyncMock(side_effect=[empty_resp, q3_resp])

    result = await scraper.fetch_shares_outstanding("005930", year=2025)

    assert result is not None
    assert result.report_type == ReportType.Q3
    assert result.shares_outstanding == 1_000_000
    assert scraper.fetch.call_count == 2


async def test_dart_fetch_shares_outstanding_none_when_no_report_has_data():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    empty_resp = MagicMock()
    empty_resp.json.return_value = {"status": "013"}
    scraper.fetch = AsyncMock(return_value=empty_resp)

    result = await scraper.fetch_shares_outstanding("005930", year=2025)

    assert result is None
    assert scraper.fetch.call_count == 4


async def test_dart_fetch_shares_outstanding_raises_on_quota_exhausted():
    scraper = DartScraper(api_key="test_key")
    scraper._corp_map = {"005930": "00126380"}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "020", "message": "요청 제한 초과"}
    scraper.fetch = AsyncMock(return_value=mock_resp)

    with pytest.raises(DartQuotaExceededError):
        await scraper.fetch_shares_outstanding("005930", year=2025)


async def test_krx_scraper_init():
    scraper = KrxScraper()
    assert scraper.source == "krx"
    assert scraper.base_url == "http://data.krx.co.kr"
    assert scraper.timeout == 30.0
    assert scraper.min_delay == 1.0


_MDCSTAT01501_CSV = (
    '"종목코드","종목명","시장구분","소속부","종가","대비","등락률",'
    '"시가","고가","저가","거래량","거래대금","시가총액","상장주식수"\n'
    '"005930","삼성전자","KOSPI","-","70000","0","0.00",'
    '"70000","70000","70000","1000","70000000","417000000000000","5969782550"\n'
    '"000660","SK하이닉스","KOSPI","-","150000","0","0.00",'
    '"150000","150000","150000","500","75000000","109000000000000","728002365"\n'
)


async def test_krx_fetch_listed_shares_parses_shares():
    scraper = KrxScraper()
    scraper._get_otp = AsyncMock(return_value="otp-token")
    scraper._download_csv = AsyncMock(return_value=_MDCSTAT01501_CSV)

    shares = await scraper.fetch_listed_shares(Market.KOSPI, trd_dd="20260703")

    assert shares["005930"] == 5969782550
    assert shares["000660"] == 728002365


async def test_krx_fetch_listed_shares_empty_on_no_rows():
    scraper = KrxScraper()
    scraper._get_otp = AsyncMock(return_value="otp-token")
    scraper._download_csv = AsyncMock(return_value="")

    assert await scraper.fetch_listed_shares(Market.KOSPI) == {}


async def test_naver_scraper_init():
    scraper = NaverScraper()
    assert scraper.source == "naver"
    assert scraper.base_url == "https://m.stock.naver.com/api"
    assert scraper._client is None


def test_parse_consensus_extracts_target_and_recomm():
    payload = {
        "consensusInfo": {
            "itemCode": "005930",
            "createDate": "2026-09-03",
            "recommMean": "4.05",
            "priceTargetMean": "487,045",
        }
    }
    target_mean, recomm_mean, base_date = parse_consensus(payload)
    assert target_mean == 487045.0
    assert recomm_mean == 4.05
    assert base_date == "2026-09-03"


def test_parse_consensus_none_when_no_coverage():
    assert parse_consensus({}) == (None, None, None)
    assert parse_consensus({"consensusInfo": {}}) == (None, None, None)


def test_parse_estimate_extracts_fwd_and_prev_eps():
    payload = {
        "financeInfo": {
            "trTitleList": [
                {"isConsensus": "N", "title": "2023.12.", "key": "202312"},
                {"isConsensus": "N", "title": "2024.12.", "key": "202412"},
                {"isConsensus": "N", "title": "2025.12.", "key": "202512"},
                {"isConsensus": "Y", "title": "2026.12.", "key": "202612"},
            ],
            "rowList": [
                {
                    "title": "매출액",
                    "columns": {
                        "202512": {"value": "3,336,059"},
                        "202612": {"value": "7,395,406"},
                    },
                },
                {
                    "title": "EPS",
                    "columns": {
                        "202412": {"value": "4,950"},
                        "202512": {"value": "6,564"},
                        "202612": {"value": "48,291"},
                    },
                },
            ],
        }
    }
    fwd_eps, prev_eps, est_year = parse_estimate(payload)
    assert fwd_eps == 48291.0
    assert prev_eps == 6564.0
    assert est_year == 2026


def test_parse_estimate_none_when_no_consensus_column():
    payload = {
        "financeInfo": {
            "trTitleList": [
                {"isConsensus": "N", "title": "2025.12.", "key": "202512"},
            ],
            "rowList": [
                {"title": "EPS", "columns": {"202512": {"value": "6,564"}}},
            ],
        }
    }
    assert parse_estimate(payload) == (None, None, None)


def test_parse_estimate_none_when_no_eps_row():
    payload = {
        "financeInfo": {
            "trTitleList": [
                {"isConsensus": "Y", "title": "2026.12.", "key": "202612"},
            ],
            "rowList": [],
        }
    }
    fwd_eps, prev_eps, est_year = parse_estimate(payload)
    assert fwd_eps is None
    assert prev_eps is None
    assert est_year == 2026


async def test_naver_consensus_scraper_init():
    scraper = NaverConsensusScraper()
    assert scraper.source == "naver_consensus"
    assert scraper.base_url == "https://m.stock.naver.com/api"


async def test_naver_consensus_fetch_consensus_with_mock():
    scraper = NaverConsensusScraper()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "consensusInfo": {
            "createDate": "2026-09-03",
            "recommMean": "4.05",
            "priceTargetMean": "487,045",
        }
    }
    scraper.fetch = AsyncMock(return_value=mock_resp)

    result = await scraper.fetch_consensus("005930")
    assert result == (487045.0, 4.05, "2026-09-03")


async def test_naver_consensus_fetch_consensus_returns_none_tuple_on_error():
    scraper = NaverConsensusScraper()
    scraper.fetch = AsyncMock(side_effect=Exception("network error"))

    result = await scraper.fetch_consensus("005930")
    assert result == (None, None, None)


async def test_naver_consensus_fetch_estimate_returns_none_tuple_on_error():
    scraper = NaverConsensusScraper()
    scraper.fetch = AsyncMock(side_effect=Exception("network error"))

    result = await scraper.fetch_estimate("005930")
    assert result == (None, None, None)


async def test_base_scraper_make_id_deterministic():
    id1 = BaseScraper.make_id("dart", "005930")
    id2 = BaseScraper.make_id("dart", "005930")
    assert id1 == id2
    assert id1.startswith("dart:")
    assert len(id1) == len("dart:") + 12


async def test_base_scraper_make_id_unique():
    id1 = BaseScraper.make_id("dart", "005930")
    id2 = BaseScraper.make_id("dart", "000660")
    id3 = BaseScraper.make_id("krx", "005930")
    assert id1 != id2
    assert id1 != id3


# ----------------------------------------------------------------------
# 실응답 축약 픽스처 (tests/fixtures/*.json, 2026-10 실측)
# ----------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _no_throttle(scraper: BaseScraper) -> BaseScraper:
    scraper.min_delay = scraper.max_delay = 0.0
    return scraper


async def test_dart_fetch_dividends_uses_alot_matter_and_picks_common_stock(httpx_mock):
    scraper = _no_throttle(DartScraper(api_key="test_key"))
    scraper._corp_map = {"005930": "00126380"}
    httpx_mock.add_response(
        url=httpx.URL(
            "https://opendart.fss.or.kr/api/alotMatter.json",
            params={
                "crtfc_key": "test_key",
                "corp_code": "00126380",
                "bsns_year": "2024",
                "reprt_code": "11011",
            },
        ),
        json=_fixture("dart_alotMatter_005930_2024.json"),
    )

    div = await scraper.fetch_dividends("005930", 2024)

    assert div is not None
    assert div.ticker == "005930" and div.year == 2024
    # 보통주 행 — '주당액면가액(원)'(100) 이나 우선주(1,447) 를 집으면 안 된다
    assert div.dividend_per_share == 1446.0
    assert div.dividend_yield == 2.7  # 현금배당수익률(%) 보통주 (주식배당수익률 '-' 아님)
    assert div.payout_ratio == 29.2  # (연결)현금배당성향(%)
    assert div.total_dividends == 9810767.0  # 현금배당금총액(백만원)
    assert div.stlm_dt == "2024-12-31"


async def test_dart_fetch_dividends_none_on_non_success_status(httpx_mock):
    scraper = _no_throttle(DartScraper(api_key="test_key"))
    scraper._corp_map = {"005930": "00126380"}
    httpx_mock.add_response(
        url=httpx.URL(
            "https://opendart.fss.or.kr/api/alotMatter.json",
            params={
                "crtfc_key": "test_key",
                "corp_code": "00126380",
                "bsns_year": "2024",
                "reprt_code": "11011",
            },
        ),
        json={"status": "013", "message": "조회된 데이타가 없습니다."},
    )

    assert await scraper.fetch_dividends("005930", 2024) is None


async def test_dart_fetch_dividends_raises_on_quota_exhausted(httpx_mock):
    scraper = _no_throttle(DartScraper(api_key="test_key"))
    scraper._corp_map = {"005930": "00126380"}
    httpx_mock.add_response(json={"status": "020", "message": "요청 제한을 초과하였습니다."})

    with pytest.raises(DartQuotaExceededError):
        await scraper.fetch_dividends("005930", 2024)


async def test_naver_fetch_stock_info_reads_ratios_from_integration(httpx_mock):
    scraper = _no_throttle(NaverScraper())
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/005930/basic",
        json=_fixture("naver_basic_005930.json"),
    )
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/005930/integration",
        json=_fixture("naver_integration_005930.json"),
    )

    r = await scraper.fetch_stock_info("005930")

    assert r is not None
    assert r.name == "삼성전자"
    assert r.market == Market.KOSPI
    assert r.price == 217000.0  # basic.closePrice
    assert r.per == 9.73  # "9.73배"
    assert r.pbr == 2.52
    assert r.eps == 22292.0  # "22,292원"
    assert r.bps == 86052.0
    assert r.dividend_yield == 0.77  # "0.77%"
    assert r.market_cap == 12686425.0  # "1,268조 6,425억" → 억원
    assert r.volume == 31811929
    assert r.high_52w == 380000.0
    assert r.low_52w == 93500.0
    assert r.foreign_ratio == 45.98  # "45.98%"


async def test_naver_fetch_stock_info_kosdaq_prefers_adjusted_52w(httpx_mock):
    scraper = _no_throttle(NaverScraper())
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/247540/basic",
        json=_fixture("naver_basic_247540.json"),
    )
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/247540/integration",
        json=_fixture("naver_integration_247540.json"),
    )

    r = await scraper.fetch_stock_info("247540")

    assert r is not None
    assert r.market == Market.KOSDAQ
    assert r.market_cap == 104189.0  # "10조 4,189억"
    assert r.per == 238.26
    assert r.high_52w == 255907.0  # highPriceOf52WeeksAdjusted, 원주가 기준(260,000) 아님
    assert r.low_52w == 86910.0


async def test_naver_fetch_stock_info_none_when_integration_fails(httpx_mock):
    scraper = _no_throttle(NaverScraper())
    scraper.max_retries = 1
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/005930/basic",
        json=_fixture("naver_basic_005930.json"),
    )
    httpx_mock.add_response(
        url="https://m.stock.naver.com/api/stock/005930/integration", status_code=500,
    )

    assert await scraper.fetch_stock_info("005930") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("9.73배", 9.73),
        ("22,292원", 22292.0),
        ("0.77%", 0.77),
        ("31,811,929", 31811929.0),
        ("-", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_unit_number(raw, expected):
    assert parse_unit_number(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,268조 6,425억", 12686425.0),
        ("10조 4,189억", 104189.0),
        ("651억", 651.0),
        ("6조 8,818억", 68818.0),
        ("-", None),
        (None, None),
    ],
)
def test_parse_krw_eok(raw, expected):
    assert parse_krw_eok(raw) == expected
