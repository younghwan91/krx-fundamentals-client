from __future__ import annotations

import io
import logging
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta

from krx_fundamentals_client.models.schemas import (
    Company,
    Dividend,
    Executive,
    FinancialStatement,
    Market,
    ReportType,
    Shareholder,
)
from krx_fundamentals_client.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

#: DART 응답 status. 일한도 소진 시 이 값이 온다.
QUOTA_EXHAUSTED_STATUS = "020"


class DartQuotaExceededError(Exception):
    """DART API 키가 일한도(020)를 소진했다.

    호출부(예: 여러 키를 순환하는 상위 오케스트레이터)가 "해당 조건에
    데이터가 없었다"(그 외 실패 status, 조용히 빈 값 반환)와 "한도 초과로
    못 가져왔다"를 구분할 수 있도록 별도 예외로 알린다 — 둘 다 빈 값으로
    뭉개면 재무제표 수집 파이프라인에 조용한 결측이 생긴다.
    """

REPORT_CODE: dict[ReportType, str] = {
    ReportType.ANNUAL: "11011",
    ReportType.HALF: "11012",
    ReportType.Q1: "11013",
    ReportType.Q3: "11014",
}

CORP_CLS_TO_MARKET: dict[str, Market] = {
    "Y": Market.KOSPI,
    "K": Market.KOSDAQ,
    "N": Market.KONEX,
}

# 재무제표 계정명 → 필드명 매핑
ACCOUNT_MAP: dict[str, str] = {
    "매출액": "revenue",
    "수익(매출액)": "revenue",
    "영업수익": "revenue",
    "영업이익": "operating_income",
    "영업이익(손실)": "operating_income",
    "당기순이익": "net_income",
    "당기순이익(손실)": "net_income",
    "분기순이익": "net_income",
    "반기순이익": "net_income",
    "자산총계": "total_assets",
    "부채총계": "total_liabilities",
    "자본총계": "total_equity",
}

#: fnlttMultiAcnt 1회 호출당 종목 상한 — 초과 시 status=021
#: ("조회 가능한 회사 개수 초과")를 돌려준다.
MULTI_BATCH_SIZE = 100


def _parse_amount(value: str | None) -> float | None:
    """쉼표가 포함된 금액 문자열을 float으로 변환."""
    if not value or value.strip() in ("", "-"):
        return None
    try:
        return float(value.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_int(value: str | None) -> int:
    """쉼표가 포함된 정수 문자열을 int로 변환."""
    if not value or value.strip() in ("", "-"):
        return 0
    try:
        return int(value.replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _parse_float(value: str | None) -> float | None:
    """쉼표가 포함된 실수 문자열을 float으로 변환."""
    if not value or value.strip() in ("", "-"):
        return None
    try:
        return float(value.replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_financial_rows(rows: list[dict]) -> dict[str, float | None]:
    """fnlttSinglAcnt/fnlttMultiAcnt 응답의 한 종목분 ``list`` 행을 필드별로 뽑는다.

    CFS(연결) 값이 이미 있으면 OFS(개별)로 덮어쓰지 않는다 — 같은 계정이
    연결·개별 두 벌로 오는 경우 연결을 우선한다.
    """
    values: dict[str, float | None] = {}
    for row in rows:
        fs_div = row.get("fs_div", "")
        account_nm = row.get("account_nm", "").strip()
        field = ACCOUNT_MAP.get(account_nm)
        if not field:
            continue
        if field in values and fs_div == "OFS":
            continue
        values[field] = _parse_amount(row.get("thstrm_amount"))
    return values


class DartScraper(BaseScraper):
    source: str = "dart"
    base_url: str = "https://opendart.fss.or.kr/api"
    min_delay: float = 0.3
    max_delay: float = 1.0

    def __init__(self, api_key: str) -> None:
        super().__init__()
        self.api_key = api_key
        self._corp_map: dict[str, str] = {}
        self._corp_map_loaded_at: datetime | None = None

    # ------------------------------------------------------------------
    # API key check
    # ------------------------------------------------------------------

    def _check_api_key(self) -> bool:
        if not self.api_key:
            logger.warning("[dart] DART API key is not configured")
            return False
        return True

    # ------------------------------------------------------------------
    # DART 응답 검증
    # ------------------------------------------------------------------

    @staticmethod
    def _check_response(data: dict, context: str = "") -> bool:
        """DART API 응답의 status를 확인. 정상(000)이면 True.

        일한도 소진(020)은 False 대신 DartQuotaExceededError 를 던진다 —
        호출부가 여러 키를 순환할 때 "그냥 데이터 없음"과 구분해야 한다.
        """
        status = data.get("status", "")
        if status == QUOTA_EXHAUSTED_STATUS:
            suffix = f", {context}" if context else ""
            raise DartQuotaExceededError(f"DART API key exhausted daily quota (status=020{suffix})")
        if status != "000":
            msg = data.get("message", "unknown error")
            logger.warning("[dart] %s — status=%s, message=%s", context, status, msg)
            return False
        return True

    # ------------------------------------------------------------------
    # 1. Corp Code Mapping (고유번호 매핑)
    # ------------------------------------------------------------------

    async def load_corp_codes(self) -> dict[str, str]:
        """corpCode.xml ZIP을 다운로드하여 {stock_code: corp_code} 매핑을 반환."""
        if not self._check_api_key():
            return {}

        # 캐시가 유효하면 재사용
        if (
            self._corp_map
            and self._corp_map_loaded_at
            and datetime.now() - self._corp_map_loaded_at < timedelta(days=1)
        ):
            return self._corp_map

        url = f"{self.base_url}/corpCode.xml"
        try:
            resp = await self.fetch(url, params={"crtfc_key": self.api_key})
        except Exception:
            logger.exception("[dart] Failed to download corp code ZIP")
            return self._corp_map

        mapping: dict[str, str] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                names = zf.namelist()
                xml_bytes = zf.read(names[0])
            root = ET.fromstring(xml_bytes)
            for item in root.iter("list"):
                corp_code = (item.findtext("corp_code") or "").strip()
                stock_code = (item.findtext("stock_code") or "").strip()
                if stock_code and corp_code:
                    mapping[stock_code] = corp_code
        except zipfile.BadZipFile:
            # 일한도 소진 등 오류 시 ZIP 대신 JSON 오류 payload 가 온다.
            try:
                data = resp.json()
            except Exception:
                data = {}
            self._check_response(data, "corp_codes")
            logger.error("[dart] corp code download returned non-ZIP payload: %s", data)
            return self._corp_map
        except Exception:
            logger.exception("[dart] Failed to parse corp code XML")
            return self._corp_map

        self._corp_map = mapping
        self._corp_map_loaded_at = datetime.now()
        logger.info("[dart] Loaded %d corp code mappings", len(mapping))
        return self._corp_map

    def get_corp_map(self) -> dict[str, str]:
        """현재 캐시된 corp_code 매핑 반환."""
        return self._corp_map

    async def _get_corp_code(self, ticker: str) -> str | None:
        """티커에 대응하는 DART 고유번호를 반환."""
        if not self._corp_map:
            await self.load_corp_codes()
        code = self._corp_map.get(ticker)
        if not code:
            logger.debug("[dart] No corp_code found for ticker=%s", ticker)
        return code

    # ------------------------------------------------------------------
    # 2. Company Info (기업개황)
    # ------------------------------------------------------------------

    async def fetch_company(self, ticker: str) -> Company | None:
        if not self._check_api_key():
            return None

        corp_code = await self._get_corp_code(ticker)
        if not corp_code:
            return None

        url = f"{self.base_url}/company.json"
        try:
            resp = await self.fetch(
                url,
                params={"crtfc_key": self.api_key, "corp_code": corp_code},
            )
        except Exception:
            logger.exception("[dart] Failed to fetch company info for %s", ticker)
            return None

        data = resp.json()
        if not self._check_response(data, f"company({ticker})"):
            return None

        corp_cls = data.get("corp_cls", "")
        acc_mt = data.get("acc_mt", "12")
        try:
            fiscal_month = int(acc_mt)
        except (ValueError, TypeError):
            fiscal_month = 12

        return Company(
            ticker=ticker,
            corp_code=corp_code,
            name=data.get("corp_name", ""),
            name_en=data.get("corp_name_eng", ""),
            market=CORP_CLS_TO_MARKET.get(corp_cls),
            industry=data.get("induty_code", ""),
            ceo=data.get("ceo_nm", ""),
            address=data.get("adres", ""),
            website=data.get("hm_url", ""),
            ir_url=data.get("ir_url", ""),
            established_date=data.get("est_dt", ""),
            fiscal_month=fiscal_month,
        )

    # ------------------------------------------------------------------
    # 3. Financial Statements (재무제표)
    # ------------------------------------------------------------------

    async def fetch_financials(
        self, ticker: str, year: int, report_type: ReportType = ReportType.ANNUAL,
    ) -> FinancialStatement | None:
        if not self._check_api_key():
            return None

        corp_code = await self._get_corp_code(ticker)
        if not corp_code:
            return None

        reprt_code = REPORT_CODE[report_type]
        url = f"{self.base_url}/fnlttSinglAcnt.json"
        try:
            resp = await self.fetch(
                url,
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": reprt_code,
                },
            )
        except Exception:
            logger.exception(
                "[dart] Failed to fetch financials for %s/%d/%s",
                ticker, year, report_type,
            )
            return None

        data = resp.json()
        if not self._check_response(data, f"financials({ticker},{year},{report_type})"):
            return None

        values = _parse_financial_rows(data.get("list", []))

        return FinancialStatement(
            ticker=ticker,
            year=year,
            report_type=report_type,
            revenue=values.get("revenue"),
            operating_income=values.get("operating_income"),
            net_income=values.get("net_income"),
            total_assets=values.get("total_assets"),
            total_liabilities=values.get("total_liabilities"),
            total_equity=values.get("total_equity"),
        )

    async def fetch_financials_batch(
        self, tickers: list[str], year: int, report_type: ReportType = ReportType.ANNUAL,
    ) -> dict[str, FinancialStatement | None]:
        """여러 종목의 재무제표를 ``fnlttMultiAcnt`` 배치 호출로 한 번에 가져온다.

        DART 문서상 호출당 최대 :data:`MULTI_BATCH_SIZE` 종목까지 comma-join 해
        보낼 수 있다 — 종목별로 ``fnlttSinglAcnt``를 반복 호출하는 대신, 전체
        상장 종목을 이 배치로 훑으면 호출 수가 크게 준다 (예: 2,600여 종목 ×
        분기 4개 ≈ 10,400회 → 배치 27개 × 4 ≈ 108회). ``tickers``가
        ``MULTI_BATCH_SIZE``를 넘으면 내부에서 자동으로 나눠 호출한다.

        결과에 없는 종목(해당 분기 공시가 없거나 corp_code를 못 찾은 경우)은
        ``None``으로 채워 넣는다 — 호출자가 KeyError 없이 순회할 수 있다.
        """
        result: dict[str, FinancialStatement | None] = dict.fromkeys(tickers, None)
        if not self._check_api_key():
            return result

        reprt_code = REPORT_CODE[report_type]

        for i in range(0, len(tickers), MULTI_BATCH_SIZE):
            batch = tickers[i : i + MULTI_BATCH_SIZE]
            corp_to_ticker: dict[str, str] = {}
            for ticker in batch:
                corp_code = await self._get_corp_code(ticker)
                if corp_code:
                    corp_to_ticker[corp_code] = ticker
            if not corp_to_ticker:
                continue

            url = f"{self.base_url}/fnlttMultiAcnt.json"
            try:
                resp = await self.fetch(
                    url,
                    params={
                        "crtfc_key": self.api_key,
                        "corp_code": ",".join(corp_to_ticker),
                        "bsns_year": str(year),
                        "reprt_code": reprt_code,
                    },
                )
            except Exception:
                logger.exception(
                    "[dart] Failed to fetch financials batch (%d tickers, %d/%s)",
                    len(batch), year, report_type,
                )
                continue

            data = resp.json()
            if not self._check_response(data, f"financials_batch({year},{report_type})"):
                continue

            by_corp: dict[str, list[dict]] = {}
            for item in data.get("list", []):
                by_corp.setdefault(item.get("corp_code", ""), []).append(item)

            for corp_code, ticker in corp_to_ticker.items():
                rows = by_corp.get(corp_code)
                if not rows:
                    continue
                values = _parse_financial_rows(rows)
                result[ticker] = FinancialStatement(
                    ticker=ticker,
                    year=year,
                    report_type=report_type,
                    revenue=values.get("revenue"),
                    operating_income=values.get("operating_income"),
                    net_income=values.get("net_income"),
                    total_assets=values.get("total_assets"),
                    total_liabilities=values.get("total_liabilities"),
                    total_equity=values.get("total_equity"),
                )

        return result

    # ------------------------------------------------------------------
    # 4. Dividends (배당)
    # ------------------------------------------------------------------

    async def fetch_dividends(self, ticker: str, year: int) -> Dividend | None:
        if not self._check_api_key():
            return None

        corp_code = await self._get_corp_code(ticker)
        if not corp_code:
            return None

        url = f"{self.base_url}/alotDvdnd.json"
        try:
            resp = await self.fetch(
                url,
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": "11011",
                },
            )
        except Exception:
            logger.exception(
                "[dart] Failed to fetch dividends for %s/%d", ticker, year,
            )
            return None

        data = resp.json()
        if not self._check_response(data, f"dividends({ticker},{year})"):
            return None

        items: list[dict] = data.get("list", [])

        dividend_per_share: float | None = None
        dividend_yield: float | None = None
        payout_ratio: float | None = None

        for item in items:
            se = item.get("se", "")
            thstrm = item.get("thstrm", "")

            if "주당" in se and dividend_per_share is None:
                dividend_per_share = _parse_float(thstrm)
            elif "배당수익률" in se and dividend_yield is None:
                dividend_yield = _parse_float(thstrm)
            elif "배당성향" in se and payout_ratio is None:
                payout_ratio = _parse_float(thstrm)

        return Dividend(
            ticker=ticker,
            year=year,
            dividend_per_share=dividend_per_share,
            dividend_yield=dividend_yield,
            payout_ratio=payout_ratio,
        )

    # ------------------------------------------------------------------
    # 5. Major Shareholders (최대주주)
    # ------------------------------------------------------------------

    async def fetch_shareholders(self, ticker: str, year: int) -> list[Shareholder]:
        if not self._check_api_key():
            return []

        corp_code = await self._get_corp_code(ticker)
        if not corp_code:
            return []

        url = f"{self.base_url}/hyslrSttus.json"
        try:
            resp = await self.fetch(
                url,
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": "11011",
                },
            )
        except Exception:
            logger.exception(
                "[dart] Failed to fetch shareholders for %s/%d", ticker, year,
            )
            return []

        data = resp.json()
        if not self._check_response(data, f"shareholders({ticker},{year})"):
            return []

        results: list[Shareholder] = []
        for item in data.get("list", []):
            name = (item.get("nm") or "").strip()
            if not name:
                continue
            results.append(
                Shareholder(
                    ticker=ticker,
                    name=name,
                    shares=_parse_int(item.get("trmend_posesn_stock_co")),
                    ownership_pct=_parse_float(item.get("trmend_posesn_stock_qota_rt")) or 0.0,
                    report_date=f"{year}",
                )
            )
        return results

    # ------------------------------------------------------------------
    # 6. Executives (임원)
    # ------------------------------------------------------------------

    async def fetch_executives(self, ticker: str, year: int) -> list[Executive]:
        if not self._check_api_key():
            return []

        corp_code = await self._get_corp_code(ticker)
        if not corp_code:
            return []

        url = f"{self.base_url}/exctvSttus.json"
        try:
            resp = await self.fetch(
                url,
                params={
                    "crtfc_key": self.api_key,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": "11011",
                },
            )
        except Exception:
            logger.exception(
                "[dart] Failed to fetch executives for %s/%d", ticker, year,
            )
            return []

        data = resp.json()
        if not self._check_response(data, f"executives({ticker},{year})"):
            return []

        results: list[Executive] = []
        for item in data.get("list", []):
            name = (item.get("nm") or "").strip()
            if not name:
                continue
            registered_raw = (item.get("rgist_exctv_at") or "").strip()
            results.append(
                Executive(
                    ticker=ticker,
                    name=name,
                    birth_year=item.get("birth_ym", ""),
                    gender=item.get("sexdstn", ""),
                    position=item.get("ofcps", ""),
                    role=item.get("main_work", ""),
                    tenure=item.get("term_end_on", ""),
                    is_registered=registered_raw == "등기임원",
                )
            )
        return results

    # ------------------------------------------------------------------
    # Main scrape
    # ------------------------------------------------------------------

    async def scrape(self) -> dict:
        """전체 DART 데이터를 수집하여 dict로 반환."""
        empty = {
            "companies": [], "financials": [], "dividends": [],
            "shareholders": [], "executives": [],
        }
        if not self._check_api_key():
            return empty

        await self.load_corp_codes()
        if not self._corp_map:
            logger.warning("[dart] No corp code mappings loaded, aborting scrape")
            return empty

        current_year = datetime.now().year
        tickers = list(self._corp_map.keys())
        logger.info("[dart] Starting scrape for %d tickers", len(tickers))

        companies: list[Company] = []
        financials: list[FinancialStatement] = []
        dividends: list[Dividend] = []
        shareholders: list[Shareholder] = []
        executives: list[Executive] = []

        for ticker in tickers:
            # 기업개황
            company = await self.fetch_company(ticker)
            if company:
                companies.append(company)

            # 재무제표 (직전 사업연도, 연간)
            fs = await self.fetch_financials(ticker, current_year - 1, ReportType.ANNUAL)
            if fs:
                financials.append(fs)

            # 배당
            div = await self.fetch_dividends(ticker, current_year - 1)
            if div:
                dividends.append(div)

            # 최대주주
            sh = await self.fetch_shareholders(ticker, current_year - 1)
            shareholders.extend(sh)

            # 임원
            ex = await self.fetch_executives(ticker, current_year - 1)
            executives.extend(ex)

        logger.info(
            "[dart] Scrape complete — companies=%d, financials=%d, dividends=%d, "
            "shareholders=%d, executives=%d",
            len(companies), len(financials), len(dividends),
            len(shareholders), len(executives),
        )

        return {
            "companies": companies,
            "financials": financials,
            "dividends": dividends,
            "shareholders": shareholders,
            "executives": executives,
        }
