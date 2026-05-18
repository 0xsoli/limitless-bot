import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

logger = logging.getLogger(__name__)

BASE_URL = "https://api.limitless.exchange"
MIN_DELAY_BETWEEN_CALLS = 0.31
MAX_CONCURRENT_REQUESTS = 2


class RateLimiter:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        self._last_call_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < MIN_DELAY_BETWEEN_CALLS:
                await asyncio.sleep(MIN_DELAY_BETWEEN_CALLS - elapsed)
            self._last_call_time = time.monotonic()
        await self._semaphore.acquire()

    def release(self):
        self._semaphore.release()


class LimitlessClient:
    def __init__(self, token_id: str, secret: str):
        self._token_id = token_id
        self._secret = secret
        self._rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers={"Content-Type": "application/json"},
            )
        return self._session

    def _sign(self, method: str, path: str, body: str = "") -> dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = f"{timestamp}\n{method}\n{path}\n{body}"
        signature = base64.b64encode(
            hmac.new(
                base64.b64decode(self._secret),
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        return {
            "lmts-api-key": self._token_id,
            "lmts-timestamp": timestamp,
            "lmts-signature": signature,
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        retries: int = 3,
    ) -> Any:
        query_string = ""
        if params:
            from urllib.parse import urlencode
            query_string = "?" + urlencode(params)

        full_path = path + query_string
        body_str = json.dumps(body) if body else ""

        for attempt in range(retries):
            await self._rate_limiter.acquire()
            try:
                session = await self._get_session()
                headers = self._sign(method, full_path, body_str)
                if body:
                    headers["Content-Type"] = "application/json"

                async with session.request(
                    method,
                    full_path,
                    headers=headers,
                    data=body_str if body else None,
                ) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 1.0))
                        logger.warning(f"Rate limited. Waiting {retry_after}s before retry {attempt + 1}")
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error {resp.status}. Retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
            finally:
                self._rate_limiter.release()

        raise RuntimeError(f"Request failed after {retries} attempts: {method} {path}")

    async def get_active_markets(self, page: int = 1, limit: int = 20, trade_type: str = None) -> dict:
        params = {"page": page, "limit": limit}
        if trade_type:
            params["tradeType"] = trade_type
        return await self._request("GET", "/markets/active", params=params)

    async def get_active_markets_by_category(self, category_id: int, page: int = 1, limit: int = 20) -> dict:
        return await self._request("GET", f"/markets/active/{category_id}", params={"page": page, "limit": limit})

    async def get_market(self, slug: str) -> dict:
        return await self._request("GET", f"/markets/{slug}")

    async def get_active_slugs(self) -> dict:
        return await self._request("GET", "/markets/active-slugs")

    async def search_markets(self, query: str) -> dict:
        return await self._request("GET", "/markets/search", params={"query": query})

    async def get_orderbook(self, slug: str) -> dict:
        return await self._request("GET", f"/markets/{slug}/orderbook")

    async def get_portfolio_positions(self) -> dict:
        return await self._request("GET", "/portfolio/positions")

    async def get_portfolio_history(self) -> dict:
        return await self._request("GET", "/portfolio/history")

    async def get_pnl_chart(self) -> dict:
        return await self._request("GET", "/portfolio/pnl-chart")

    async def get_profile(self, account: str) -> dict:
        return await self._request("GET", f"/profiles/{account}")

    async def get_points(self) -> dict:
        return await self._request("GET", "/portfolio/points")

    async def get_user_orders(self, slug: str) -> dict:
        return await self._request("GET", f"/markets/{slug}/user-orders")

    async def create_order(self, payload: dict) -> dict:
        return await self._request("POST", "/orders", body=payload)

    async def cancel_order(self, order_id: str) -> dict:
        return await self._request("DELETE", f"/orders/{order_id}")

    async def cancel_all_orders(self) -> dict:
        return await self._request("DELETE", "/orders")

    async def get_historical_prices(self, slug: str, interval: str = "1h") -> dict:
        return await self._request(
            "GET", f"/markets/{slug}/prices/history", params={"interval": interval}
        )

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
