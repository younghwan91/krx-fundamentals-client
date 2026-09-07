from __future__ import annotations

import asyncio
import hashlib
import logging
import random
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


def parse_float(value: object) -> float | None:
    """쉼표 포함 숫자 문자열(또는 float/int)을 float으로 변환. 빈 값/``-``/``N/A``는 None."""
    if value is None:
        return None
    text = str(value).strip()
    if text in ("", "-", "N/A"):
        return None
    try:
        return float(text.replace(",", ""))
    except (ValueError, TypeError):
        return None


def parse_int(value: object, default: int | None = None) -> int | None:
    """쉼표 포함 숫자 문자열(또는 float/int)을 int로 변환. 실패 시 ``default``."""
    parsed = parse_float(value)
    return default if parsed is None else int(parsed)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
]


class BaseScraper(ABC):
    source: str
    base_url: str = ""
    min_delay: float = 0.5
    max_delay: float = 2.0
    timeout: float = 15.0
    max_retries: int = 3

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": random.choice(USER_AGENTS)},
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _throttle(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        client = await self.get_client()
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                await self._throttle()
                resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                last_exc = e
                wait = 2**attempt + random.random()
                logger.warning(
                    "[%s] %s %s attempt %d failed: %s, retry in %.1fs",
                    self.source, method, url, attempt, e, wait,
                )
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]

    async def fetch(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("GET", url, **kwargs)

    async def fetch_post(self, url: str, **kwargs) -> httpx.Response:
        return await self._request("POST", url, **kwargs)

    @staticmethod
    def make_id(source: str, unique_key: str) -> str:
        h = hashlib.md5(unique_key.encode()).hexdigest()[:12]
        return f"{source}:{h}"

    @abstractmethod
    async def scrape(self) -> dict:
        """각 스크래퍼가 구현할 메인 수집 메서드. 결과를 dict로 반환."""
        ...
