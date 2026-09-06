from __future__ import annotations

import logging

from krx_fundamentals_client.models.schemas import InvestmentRatio, Market
from krx_fundamentals_client.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


def _parse_float(value: object) -> float | None:
    """문자열·숫자·None 을 float | None 으로 변환. 쉼표 제거 포함."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


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


class NaverScraper(BaseScraper):
    """네이버 금융 모바일 JSON API 기반 투자지표 수집 스크래퍼."""

    source = "naver"
    base_url = "https://m.stock.naver.com/api"
    min_delay = 0.3
    max_delay = 1.0

    async def fetch_stock_info(self, ticker: str) -> InvestmentRatio | None:
        """단일 종목의 기본 투자지표를 모바일 JSON API에서 수집한다."""
        url = f"{self.base_url}/stock/{ticker}/basic"
        try:
            resp = await self.fetch(url)
            data = resp.json()
        except Exception:
            logger.warning("[%s] Failed to fetch ticker %s", self.source, ticker)
            return None

        try:
            return InvestmentRatio(
                ticker=ticker,
                name=data.get("stockName", ""),
                market=_detect_market(data.get("marketName")),
                market_cap=_parse_float(data.get("marketCap")),
                per=_parse_float(data.get("per")),
                pbr=_parse_float(data.get("pbr")),
                eps=_parse_float(data.get("eps")),
                bps=_parse_float(data.get("bps")),
                dividend_yield=_parse_float(data.get("dividendYield")),
                price=_parse_float(data.get("closePrice")),
                volume=_parse_int(data.get("accumulatedTradingVolume")),
                high_52w=_parse_float(data.get("high52wPrice")),
                low_52w=_parse_float(data.get("low52wPrice")),
                foreign_ratio=_parse_float(data.get("foreignRatio")),
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
