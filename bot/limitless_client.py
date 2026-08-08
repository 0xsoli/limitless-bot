import asyncio
import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import aiohttp
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address

logger = logging.getLogger(__name__)

BASE_URL = "https://api.limitless.exchange"
CHAIN_ID = 8453
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
MIN_DELAY_BETWEEN_CALLS = 0.31
MAX_CONCURRENT_REQUESTS = 2
SCALE = 1_000_000


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
    def __init__(self, token_id: str, secret: str, private_key: str = ""):
        self._token_id = token_id
        self._secret = secret
        self._private_key = private_key.strip() if private_key else ""
        self._account = Account.from_key(self._private_key) if self._private_key else None
        self._rate_limiter = RateLimiter()
        self._session: Optional[aiohttp.ClientSession] = None
        self._profile: Optional[dict] = None
        self._owner_id: Optional[int] = None
        self._fee_rate_bps: int = 0

    @property
    def address(self) -> str:
        if not self._account:
            return ""
        return self._account.address

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=BASE_URL,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
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
        auth: bool = True,
    ) -> Any:
        query_string = ""
        if params:
            clean = {k: v for k, v in params.items() if v is not None}
            if clean:
                query_string = "?" + urlencode(clean, doseq=True)

        full_path = path + query_string
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""

        last_error: Optional[Exception] = None
        for attempt in range(retries):
            await self._rate_limiter.acquire()
            try:
                session = await self._get_session()
                headers = self._sign(method, full_path, body_str) if auth else {}
                if body is not None:
                    headers["Content-Type"] = "application/json"

                async with session.request(
                    method,
                    full_path,
                    headers=headers,
                    data=body_str if body is not None else None,
                ) as resp:
                    text = await resp.text()

                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", 1.0))
                        logger.warning("Rate limited. Waiting %ss", retry_after)
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status >= 500:
                        wait_time = 2 ** attempt
                        logger.warning("Server error %s. Retrying in %ss", resp.status, wait_time)
                        await asyncio.sleep(wait_time)
                        continue

                    if resp.status >= 400:
                        message = text
                        try:
                            err = json.loads(text) if text else {}
                            if isinstance(err, dict):
                                message = err.get("message") or err.get("error") or text
                                if isinstance(message, list):
                                    message = "; ".join(str(x) for x in message)
                        except json.JSONDecodeError:
                            pass
                        raise RuntimeError(f"API {resp.status}: {message}")

                    if not text:
                        return {}
                    return json.loads(text)
            except aiohttp.ClientError as e:
                last_error = e
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                logger.warning("Request failed (attempt %s): %s", attempt + 1, e)
            finally:
                self._rate_limiter.release()

        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed after {retries} attempts: {method} {path}")

    async def get_profile_me(self) -> dict:
        profile = await self._request("GET", "/profiles/me")
        self._profile = profile
        self._owner_id = int(profile["id"])
        rank = profile.get("rank") or {}
        self._fee_rate_bps = int(rank.get("feeRateBps") or 0)
        return profile

    async def ensure_ready(self) -> dict:
        profile = await self.get_profile_me()
        if profile.get("tradeWalletOption") == "smartWallet":
            await self._request("PUT", "/profiles", body={"tradeWalletOption": "eoa"})
            profile = await self.get_profile_me()
        return profile

    async def get_navigation(self) -> list:
        return await self._request("GET", "/navigation", auth=False)

    async def get_market_page_by_path(self, path: str) -> dict:
        return await self._request("GET", "/market-pages/by-path", params={"path": path}, auth=False)

    async def get_page_markets(
        self,
        page_id: str,
        page: int = 1,
        limit: int = 15,
        sort: str = "-updatedAt",
        filters: Optional[dict] = None,
    ) -> dict:
        params: dict[str, Any] = {"page": page, "limit": limit, "sort": sort}
        if filters:
            params.update(filters)
        return await self._request("GET", f"/market-pages/{page_id}/markets", params=params, auth=False)

    async def get_active_markets(
        self,
        page: int = 1,
        limit: int = 25,
        trade_type: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> dict:
        params: dict[str, Any] = {"page": page, "limit": min(limit, 25)}
        if trade_type:
            params["tradeType"] = trade_type
        if category_id is not None:
            params["categoryId"] = category_id
        return await self._request("GET", "/markets/active", params=params, auth=False)

    async def get_category_counts(self) -> dict:
        return await self._request("GET", "/markets/categories/count", auth=False)

    async def get_market(self, slug: str) -> dict:
        return await self._request("GET", f"/markets/{slug}", auth=False)

    async def get_orderbook(self, slug: str) -> dict:
        return await self._request("GET", f"/markets/{slug}/orderbook", auth=False)

    async def get_portfolio_positions(self) -> Any:
        return await self._request("GET", "/portfolio/positions")

    async def get_portfolio_history(self) -> Any:
        return await self._request("GET", "/portfolio/history")

    async def get_pnl_chart(self) -> Any:
        return await self._request("GET", "/portfolio/pnl-chart")

    async def get_profile(self, account: str) -> dict:
        return await self._request("GET", f"/profiles/{account}")

    async def get_points(self) -> Any:
        return await self._request("GET", "/portfolio/points")

    async def get_user_orders(self, slug: str) -> Any:
        return await self._request("GET", f"/markets/{slug}/user-orders")

    async def cancel_order(self, order_id: str) -> Any:
        return await self._request("DELETE", f"/orders/{order_id}")

    async def cancel_all_orders(self, market_slug: str) -> Any:
        if not market_slug:
            raise ValueError("market_slug is required to cancel all orders")
        return await self._request("DELETE", f"/orders/all/{market_slug}")

    def _resolve_token_id(self, market: dict, outcome: str) -> str:
        outcome = outcome.upper()
        tokens = market.get("tokens") or {}
        if isinstance(tokens, dict):
            key = "yes" if outcome == "YES" else "no"
            token_id = tokens.get(key) or tokens.get(key.upper()) or tokens.get(key.capitalize())
            if token_id:
                return str(token_id)
        yes_id = market.get("yesPositionId") or market.get("yesTokenId")
        no_id = market.get("noPositionId") or market.get("noTokenId")
        if outcome == "YES" and yes_id:
            return str(yes_id)
        if outcome == "NO" and no_id:
            return str(no_id)
        raise RuntimeError(f"Could not resolve token ID for outcome {outcome}")

    def _resolve_exchange(self, market: dict) -> str:
        venue = market.get("venue") or {}
        exchange = venue.get("exchange") or market.get("exchange")
        if not exchange:
            raise RuntimeError("Market is missing venue.exchange required for order signing")
        return to_checksum_address(exchange)

    def _fee_rate_for_market(self, market: dict) -> int:
        metadata = market.get("metadata") or {}
        if metadata.get("fee"):
            return int(self._fee_rate_bps)
        return 0

    def _build_amounts(
        self,
        side: int,
        order_type: str,
        price: Optional[float],
        size: Optional[float],
        maker_amount_human: Optional[float],
    ) -> tuple[int, int, Optional[float]]:
        order_type = order_type.upper()
        if order_type == "FOK":
            if maker_amount_human is None or maker_amount_human <= 0:
                raise ValueError("FOK orders require a positive maker amount")
            return int(round(float(maker_amount_human) * SCALE)), 1, None

        if price is None or size is None:
            raise ValueError("GTC/FAK orders require price and size")
        if not (0.01 <= float(price) <= 0.99):
            raise ValueError("Price must be between 0.01 and 0.99")
        if float(size) <= 0:
            raise ValueError("Size must be positive")

        p = float(price)
        s = float(size)
        if side == 0:
            maker_amount = int(round(p * s * SCALE))
            taker_amount = int(round(s * SCALE))
        else:
            maker_amount = int(round(s * SCALE))
            taker_amount = int(round(p * s * SCALE))

        if maker_amount <= 0 or taker_amount <= 0:
            raise ValueError("Computed order amounts are invalid")
        return maker_amount, taker_amount, p

    def _sign_order(self, order_data: dict, verifying_contract: str) -> str:
        if not self._account or not self._private_key:
            raise RuntimeError("Wallet private key is required to sign orders")

        domain = {
            "name": "Limitless CTF Exchange",
            "version": "1",
            "chainId": CHAIN_ID,
            "verifyingContract": to_checksum_address(verifying_contract),
        }
        types = {
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "taker", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "expiration", "type": "uint256"},
                {"name": "nonce", "type": "uint256"},
                {"name": "feeRateBps", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
            ],
        }
        message = {
            "salt": int(order_data["salt"]),
            "maker": to_checksum_address(order_data["maker"]),
            "signer": to_checksum_address(order_data["signer"]),
            "taker": to_checksum_address(order_data["taker"]),
            "tokenId": int(order_data["tokenId"]),
            "makerAmount": int(order_data["makerAmount"]),
            "takerAmount": int(order_data["takerAmount"]),
            "expiration": int(order_data["expiration"]),
            "nonce": int(order_data["nonce"]),
            "feeRateBps": int(order_data["feeRateBps"]),
            "side": int(order_data["side"]),
            "signatureType": int(order_data["signatureType"]),
        }
        encoded = encode_typed_data(
            full_message={
                "types": types,
                "primaryType": "Order",
                "domain": domain,
                "message": message,
            }
        )
        signed = Account.sign_message(encoded, private_key=self._private_key)
        sig = signed.signature.hex()
        if not sig.startswith("0x"):
            sig = "0x" + sig
        return sig

    async def place_order(
        self,
        market_slug: str,
        outcome: str,
        side: str,
        order_type: str,
        price: Optional[float] = None,
        size: Optional[float] = None,
        maker_amount: Optional[float] = None,
        market: Optional[dict] = None,
    ) -> dict:
        if not self._account:
            raise RuntimeError("Wallet private key is not configured")

        if self._owner_id is None:
            await self.ensure_ready()

        if market is None:
            market = await self.get_market(market_slug)

        trade_type = str(market.get("tradeType") or "").lower()
        if trade_type and trade_type not in ("clob", "group", ""):
            raise RuntimeError(
                f"This bot places CLOB orders only. Market trade type is '{trade_type}'."
            )

        token_id = self._resolve_token_id(market, outcome)
        exchange = self._resolve_exchange(market)
        fee_rate_bps = self._fee_rate_for_market(market)
        side_int = 0 if str(side).upper() == "BUY" else 1
        order_type = order_type.upper()
        maker_amt, taker_amt, signed_price = self._build_amounts(
            side_int, order_type, price, size, maker_amount
        )

        maker = to_checksum_address(self._account.address)
        salt = int(secrets.randbits(48))
        order_data = {
            "salt": salt,
            "maker": maker,
            "signer": maker,
            "taker": ZERO_ADDRESS,
            "tokenId": str(token_id),
            "makerAmount": maker_amt,
            "takerAmount": taker_amt,
            "expiration": 0,
            "nonce": 0,
            "feeRateBps": fee_rate_bps,
            "side": side_int,
            "signatureType": 0,
        }
        signature = self._sign_order(order_data, exchange)

        order_body = {
            "salt": str(salt),
            "maker": maker,
            "signer": maker,
            "taker": ZERO_ADDRESS,
            "tokenId": str(token_id),
            "makerAmount": maker_amt,
            "takerAmount": taker_amt,
            "expiration": "0",
            "nonce": 0,
            "feeRateBps": fee_rate_bps,
            "side": side_int,
            "signatureType": 0,
            "signature": signature,
        }
        if signed_price is not None:
            order_body["price"] = signed_price

        payload = {
            "order": order_body,
            "ownerId": int(self._owner_id),
            "orderType": order_type,
            "marketSlug": market_slug,
        }
        return await self._request("POST", "/orders", body=payload)

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
