from __future__ import annotations

import logging
import re

from krx_fundamentals_client.models.schemas import InvestmentRatio, Market
from krx_fundamentals_client.scrapers.base import BaseScraper
from krx_fundamentals_client.scrapers.base import parse_float as _parse_float
from krx_fundamentals_client.scrapers.base import parse_int as _parse_int

logger = logging.getLogger(__name__)


def _detect_market(market_name: str | None) -> Market | None:
    if not market_name:
        return None
    name = market_name.upper()
    if "KOSPI" in name:
        return Market.KOSPI
    if "KOSDAQ" in name:
        return Market.KOSDAQ
    if "KONEX" in name:
        return Market.KONEX
    return None


def parse_consensus(
    payload: dict,
) -> tuple[float | None, float | None, str | None]:
    """``.../integration`` 응답에서 목표주가·투자의견 컨센서스를 뽑는다.

    ``consensusInfo``가 없거나 커버리지가 없는 종목은 전부 ``None``을 반환한다.
    """
    info = payload.get("consensusInfo") or {}
    target_mean = _parse_float(info.get("priceTargetMean"))
    recomm_mean = _parse_float(info.get("recommMean"))
    base_date = info.get("createDate") or None
    return target_mean, recomm_mean, base_date


def parse_estimate(
    payload: dict,
) -> tuple[float | None, float | None, int | None]:
    """``.../finance/annual`` 응답에서 추정 EPS(fwd)와 최근 실적 EPS(prev)를 뽑는다.

    ``trTitleList``(각 항목 ``{"isConsensus", "title", "key"}``, ``key``는
    ``"202612"``처럼 연월 문자열) 중 ``isConsensus == "Y"``인 첫 컬럼의 ``key``를
    추정연도 컬럼으로, 그 바로 이전 연도(``key`` 앞 4자리 -1)를 최근 실적연도
    컬럼으로 본다. ``rowList``에서 ``title == "EPS"``인 행의
    ``columns[key]["value"]``를 각각 fwd_eps/prev_eps로 뽑는다. 추정 컬럼을 못
    찾거나 EPS 행이 없으면 전부 ``None``을 반환한다.
    """
    info = payload.get("financeInfo") or {}
    tr_titles: list[dict] = info.get("trTitleList") or []

    est_key: str | None = None
    for title in tr_titles:
        if title.get("isConsensus") == "Y":
            est_key = title.get("key")
            break

    if est_key is None:
        return None, None, None

    try:
        est_year = int(str(est_key)[:4])
    except (ValueError, TypeError):
        return None, None, None

    prev_key = f"{est_year - 1}{str(est_key)[4:]}"

    for row in info.get("rowList") or []:
        if row.get("title") != "EPS":
            continue
        columns: dict = row.get("columns") or {}
        fwd_eps = _parse_float((columns.get(est_key) or {}).get("value"))
        prev_eps = _parse_float((columns.get(prev_key) or {}).get("value"))
        return fwd_eps, prev_eps, est_year

    return None, None, est_year


_LEADING_NUMBER = re.compile(r"^[-+]?\d[\d,]*(?:\.\d+)?|^[-+]?\.\d+")
_KRW_EOK = re.compile(r"(?:([\d,]+)\s*조)?\s*(?:([\d,]+)\s*억)?")


def parse_unit_number(value: object) -> float | None:
    """"9.73배"·"22,292원"·"0.77%" 처럼 단위가 붙은 표시 문자열에서 앞의 숫자만 뽑는다.

    숫자로 시작하지 않으면(``-``·빈 값) ``None``. 쉼표 처리는 ``parse_float`` 에 맡긴다.
    """
    if value is None:
        return None
    m = _LEADING_NUMBER.match(str(value).strip())
    return _parse_float(m.group(0)) if m else None


def parse_krw_eok(value: object) -> float | None:
    """"1,268조 6,425억"·"651억" 같은 금액 표시를 억원 float 으로. 조·억이 없으면 ``None``."""
    if value is None:
        return None
    m = _KRW_EOK.fullmatch(str(value).strip())
    if not m or not (m.group(1) or m.group(2)):
        return None
    jo = _parse_float(m.group(1)) or 0.0
    eok = _parse_float(m.group(2)) or 0.0
    return jo * 10_000 + eok


def parse_total_infos(payload: dict) -> dict:
    """``.../integration`` 의 ``totalInfos`` 를 ``InvestmentRatio`` 필드 dict 로.

    항목은 ``{"code": "per", "key": "PER", "value": "9.73배"}`` 꼴. 52주 고저는
    수정주가 기준(``...Adjusted``)이 있으면 그것을 쓴다.
    """
    info: dict[str, object] = {}
    for item in payload.get("totalInfos") or []:
        code = item.get("code")
        if code and code not in info:
            info[code] = item.get("value")

    def _first(*codes: str) -> object:
        return next((info[c] for c in codes if info.get(c) is not None), None)

    return {
        "market_cap": parse_krw_eok(info.get("marketValue")),
        "per": parse_unit_number(info.get("per")),
        "pbr": parse_unit_number(info.get("pbr")),
        "eps": parse_unit_number(info.get("eps")),
        "bps": parse_unit_number(info.get("bps")),
        "dividend_yield": parse_unit_number(info.get("dividendYieldRatio")),
        "volume": _parse_int(info.get("accumulatedTradingVolume")),
        "high_52w": parse_unit_number(_first("highPriceOf52WeeksAdjusted", "highPriceOf52Weeks")),
        "low_52w": parse_unit_number(_first("lowPriceOf52WeeksAdjusted", "lowPriceOf52Weeks")),
        "foreign_ratio": parse_unit_number(info.get("foreignRate")),
    }


class NaverScraper(BaseScraper):
    """네이버 금융 모바일 JSON API 기반 투자지표 수집 스크래퍼."""

    source = "naver"
    base_url = "https://m.stock.naver.com/api"
    min_delay = 0.3
    max_delay = 1.0

    async def fetch_stock_info(self, ticker: str) -> InvestmentRatio | None:
        """단일 종목의 투자지표를 모바일 JSON API 두 번으로 모은다.

        ``/basic`` 은 종목명·시장·현재가만 준다(2026-10 실측). PER·PBR·EPS·BPS·
        배당수익률·시총·거래량·52주 고저·외인소진율은 ``/integration`` 의
        ``totalInfos`` (``code``/``value`` 항목, 값은 "9.73배"·"1,268조 6,425억" 같은
        표시 문자열)에서 읽는다. 둘 중 하나라도 실패하면 ``None``.
        """
        try:
            basic = (await self.fetch(f"{self.base_url}/stock/{ticker}/basic")).json()
            integration = (
                await self.fetch(f"{self.base_url}/stock/{ticker}/integration")
            ).json()
        except Exception:
            logger.warning("[%s] Failed to fetch ticker %s", self.source, ticker)
            return None

        try:
            return InvestmentRatio(
                ticker=ticker,
                name=basic.get("stockName") or integration.get("stockName") or "",
                market=_detect_market(basic.get("stockExchangeName")),
                price=_parse_float(basic.get("closePrice")),
                **parse_total_infos(integration),
            )
        except Exception:
            logger.warning(
                "[%s] Failed to parse response for ticker %s",
                self.source,
                ticker,
                exc_info=True,
            )
            return None

    async def fetch_batch(
        self, tickers: list[str]
    ) -> list[InvestmentRatio]:
        """여러 종목의 투자지표를 순차적으로 수집한다 (rate-limit 준수)."""
        results: list[InvestmentRatio] = []
        total = len(tickers)

        for idx, ticker in enumerate(tickers, 1):
            ratio = await self.fetch_stock_info(ticker)
            if ratio is not None:
                results.append(ratio)

            if idx % 100 == 0:
                logger.info(
                    "[%s] Progress: %d / %d tickers fetched (%d collected)",
                    self.source,
                    idx,
                    total,
                    len(results),
                )

        logger.info(
            "[%s] Batch complete: %d / %d tickers collected",
            self.source,
            len(results),
            total,
        )
        return results

    async def scrape(self) -> dict:
        """메인 수집 메서드. 외부에서 tickers를 주입받아 호출하는 구조.

        단독 호출 시 빈 결과를 반환한다. tickers를 설정하려면
        ``scrape_tickers``를 사용하라.
        """
        return {"ratios": []}

    async def scrape_tickers(self, tickers: list[str]) -> dict:
        """주어진 ticker 목록에 대해 투자지표를 수집하여 반환한다."""
        ratios = await self.fetch_batch(tickers)
        return {"ratios": [r.model_dump() for r in ratios]}


class NaverConsensusScraper(BaseScraper):
    """네이버 금융 모바일 JSON API 기반 애널리스트 컨센서스 수집 스크래퍼.

    유니버스 선정·배치 호출·DB 적재는 호출부(오케스트레이터) 책임이고, 이
    스크래퍼는 종목 하나에 대한 fetch/parse만 담당한다.
    """

    source = "naver_consensus"
    base_url = "https://m.stock.naver.com/api"
    min_delay = 0.3
    max_delay = 1.0

    async def fetch_consensus(
        self, ticker: str
    ) -> tuple[float | None, float | None, str | None]:
        """목표주가 평균·투자의견 평균·컨센서스 기준일을 가져온다.

        커버리지가 없거나 요청이 실패하면 ``(None, None, None)``을 반환한다.
        """
        url = f"{self.base_url}/stock/{ticker}/integration"
        try:
            resp = await self.fetch(url)
            return parse_consensus(resp.json())
        except Exception:
            logger.warning(
                "[%s] Failed to fetch consensus for %s", self.source, ticker,
                exc_info=True,
            )
            return None, None, None

    async def fetch_estimate(
        self, ticker: str
    ) -> tuple[float | None, float | None, int | None]:
        """추정 EPS(fwd)·최근 실적 EPS(prev)·추정연도를 가져온다.

        추정 컨센서스가 없거나 요청이 실패하면 ``(None, None, None)``을 반환한다.
        """
        url = f"{self.base_url}/stock/{ticker}/finance/annual"
        try:
            resp = await self.fetch(url)
            return parse_estimate(resp.json())
        except Exception:
            logger.warning(
                "[%s] Failed to fetch estimate for %s", self.source, ticker,
                exc_info=True,
            )
            return None, None, None

    async def scrape(self) -> dict:
        """단독 호출 시 빈 결과를 반환한다. fetch_consensus/fetch_estimate를 직접 사용하라."""
        return {"consensus": []}
