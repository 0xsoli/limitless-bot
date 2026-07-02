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

from .order_signer import build_signed_order

logger = logging.getLogger(__name__)

BASE_URL = "https://api.limitless.exchange"
MIN_DELAY_BETWEEN_CALLS = 0.31
MAX_CONCURRENT_REQUESTS = 2
REQUEST_TIMEOUT_SECONDS = 30
ORDER_TIMEOUT_SECONDS = 60

PUBLIC_PREFIXES = (
    "/markets/active",
    "/markets/active-slugs",
    "/markets/search",
)


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


class LimitlessAPIError(Exception):
    def __init__(self, status: int, message: str, code: Optional[str] = None):
        self.status = status
        self.message = message
        self.code = code
        super().__init__(f"API error {status}: {message}")


class LimitlessClient:
    def __init__(self, token_id: str, secret: str, private_key: str = ""):
        self._token_id = token_id
        self._secret = secret
        self._private_key = private_key
        self._rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
        self._profile_cache: Optional[dict] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=REQUEST_TIMEOUT_SECONDS,
                connect=10,
                sock_connect=10,
                sock_read=REQUEST_TIMEOUT_SECONDS,
            )
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
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

    def _requires_auth(self, method: str, path: str) -> bool:
        if method.upper() != "GET":
            return True
        if path.startswith("/portfolio") or path.startswith("/profiles"):
            return True
        if path.endswith("/user-orders"):
            return True
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return False
        if path.startswith("/markets/") and "/orderbook" in path:
            return False
        if path.startswith("/markets/") and path.count("/") == 2:
            return False
        return True

    async def _parse_error(self, resp: aiohttp.ClientResponse) -> tuple[str, Optional[str]]:
        try:
            payload = await resp.json()
            if isinstance(payload, dict):
                message = (
                    payload.get("message")
                    or payload.get("error")
                    or json.dumps(payload)
                )
                code = payload.get("code")
                mode = payload.get("mode")
                resume_at = payload.get("resumeAt")
                if mode:
                    suffix = f" (mode: {mode}"
                    if resume_at:
                        suffix += f", resumes {str(resume_at)[:19]}"
                    suffix += ")"
                    message = f"{message}{suffix}"
                return message, code
        except Exception:
            pass
        try:
            return await resp.text(), None
        except Exception:
            return f"HTTP {resp.status}", None

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        body: Optional[dict] = None,
        retries: int = 3,
    ) -> Any:
        from urllib.parse import urlencode

        query_string = ""
        if params:
            query_string = "?" + urlencode(params)

        full_path = path + query_string
        body_str = json.dumps(body, separators=(",", ":")) if body else ""

        for attempt in range(retries):
            await self._rate_limiter.acquire()
            try:
                session = await self._get_session()
                headers = {}
                if self._requires_auth(method, path):
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
                        logger.warning(
                            f"Rate limited. Waiting {retry_after}s before retry {attempt + 1}"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error {resp.status}. Retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    if resp.status >= 400:
                        message, code = await self._parse_error(resp)
                        raise LimitlessAPIError(resp.status, message, code)

                    if resp.status == 204:
                        return {}
                    return await resp.json()
            except LimitlessAPIError:
                raise
            except asyncio.TimeoutError:
                raise LimitlessAPIError(
                    408,
                    f"Request timed out after {REQUEST_TIMEOUT_SECONDS}s waiting for Limitless API",
                )
            except aiohttp.ClientError as e:
                if attempt == retries - 1:
                    raise LimitlessAPIError(
                        0,
                        f"Network error contacting Limitless API: {e}",
                    ) from e
                await asyncio.sleep(2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
            finally:
                self._rate_limiter.release()

        raise RuntimeError(f"Request failed after {retries} attempts: {method} {path}")

    async def get_active_markets(self, page: int = 1, limit: int = 20, trade_type: str = "clob") -> dict:
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

    async def get_current_profile(self, force_refresh: bool = False) -> dict:
        if self._profile_cache and not force_refresh:
            return self._profile_cache
        profile = await self._request("GET", "/profiles/me")
        self._profile_cache = profile
        return profile

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

    def _resolve_token_id(self, market_data: dict, outcome: str) -> str:
        tokens = market_data.get("tokens") or market_data.get("positionIds") or {}
        outcome_key = "yes" if outcome.upper() == "YES" else "no"

        if isinstance(tokens, dict):
            token_id = tokens.get(outcome_key) or tokens.get(outcome_key.upper())
            if token_id:
                return str(token_id)

        if isinstance(tokens, list) and tokens:
            return str(tokens[0] if outcome.upper() == "YES" else tokens[min(1, len(tokens) - 1)])

        raise ValueError(f"Could not resolve {outcome} token ID for market")

    async def create_order(
        self,
        *,
        market_slug: str,
        order_type: str,
        outcome: str = "YES",
        side: int = 0,
        price: Optional[float] = None,
        size: Optional[float] = None,
        usdc_amount: Optional[float] = None,
        market_data: Optional[dict] = None,
    ) -> dict:
        if not self._private_key:
            raise ValueError("Wallet private key is required to sign orders")

        from eth_account import Account

        wallet_address = Account.from_key(self._private_key).address

        market = market_data or await self.get_market(market_slug)
        venue = market.get("venue") or {}
        exchange = venue.get("exchange")
        if not exchange:
            raise ValueError("Market does not expose venue.exchange — only CLOB markets can be traded")

        token_id = self._resolve_token_id(market, outcome)
        profile = await self.get_current_profile()
        owner_id = profile.get("id")
        if not owner_id:
            raise ValueError("Could not resolve profile id from GET /profiles/me")

        profile_account = profile.get("account", "")
        if profile_account and wallet_address.lower() != profile_account.lower():
            raise ValueError(
                "Wallet mismatch: the configured private key does not match the "
                f"Limitless API token account ({profile_account}). "
                "Use the same wallet for both."
            )

        fee_rate_bps = 0
        rank = profile.get("rank") or {}
        if isinstance(rank, dict):
            fee_rate_bps = int(rank.get("feeRateBps", 0))

        signed_order = build_signed_order(
            private_key=self._private_key,
            token_id=token_id,
            verifying_contract=exchange,
            side=side,
            order_type=order_type,
            fee_rate_bps=fee_rate_bps,
            price=price,
            size=size,
            usdc_amount=usdc_amount,
        )

        payload = {
            "order": signed_order,
            "ownerId": owner_id,
            "orderType": order_type,
            "marketSlug": market_slug,
        }
        logger.info(
            "Submitting %s order for %s %s on %s",
            order_type,
            outcome,
            "BUY" if side == 0 else "SELL",
            market_slug,
        )
        return await asyncio.wait_for(
            self._request("POST", "/orders", body=payload),
            timeout=ORDER_TIMEOUT_SECONDS,
        )

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
