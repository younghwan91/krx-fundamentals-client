from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from krx_fundamentals_client.models.schemas import Market
from krx_fundamentals_client.scrapers.base import BaseScraper
from krx_fundamentals_client.scrapers.dart import DartQuotaExceededError, DartScraper
from krx_fundamentals_client.scrapers.krx import KrxScraper
from krx_fundamentals_client.scrapers.naver import NaverScraper


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
