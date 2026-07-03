import asyncio
import logging
from typing import Callable, Optional

import socketio

from .hmac_auth import sign_websocket_handshake

logger = logging.getLogger(__name__)

WS_URL = "wss://ws.limitless.exchange"
WS_NAMESPACE = "/markets"


class WebSocketManager:
    def __init__(self, token_id: str, secret: str, bot=None):
        self._token_id = token_id
        self._secret = secret
        self._bot = bot
        self._sio: Optional[socketio.AsyncClient] = None
        self._connected = False
        self._subscribed_slugs: list[str] = []
        self._orderbook_callbacks: dict[str, Callable] = {}
        self._position_callbacks: list[Callable] = []
        self._order_callbacks: list[Callable] = []
        self._reconnect_task: Optional[asyncio.Task] = None

    async def connect(self):
        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=2,
            reconnection_delay_max=30,
        )

        @self._sio.event(namespace=WS_NAMESPACE)
        async def connect():
            self._connected = True
            logger.info("WebSocket connected")
            if self._subscribed_slugs:
                await self._resubscribe()

        @self._sio.event(namespace=WS_NAMESPACE)
        async def disconnect():
            self._connected = False
            logger.warning("WebSocket disconnected")

        @self._sio.on("orderbookUpdate", namespace=WS_NAMESPACE)
        async def on_orderbook(data):
            slug = data.get("marketSlug", "")
            orderbook = data.get("orderbook", data)
            if slug in self._orderbook_callbacks:
                await self._orderbook_callbacks[slug](orderbook)

        @self._sio.on("positions", namespace=WS_NAMESPACE)
        async def on_positions(data):
            for cb in self._position_callbacks:
                await cb(data)

        @self._sio.on("orderEvent", namespace=WS_NAMESPACE)
        async def on_order_event(data):
            for cb in self._order_callbacks:
                await cb(data)

        @self._sio.on("system", namespace=WS_NAMESPACE)
        async def on_system(data):
            logger.info(f"WS System: {data}")

        @self._sio.on("exception", namespace=WS_NAMESPACE)
        async def on_exception(data):
            logger.error(f"WS Exception: {data}")

        try:
            await self._sio.connect(
                WS_URL,
                namespaces=[WS_NAMESPACE],
                transports=["websocket"],
                headers=sign_websocket_handshake(self._token_id, self._secret),
            )
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")

    async def _resubscribe(self):
        if self._subscribed_slugs and self._connected:
            await self._sio.emit(
                "subscribe_market_prices",
                {"marketSlugs": self._subscribed_slugs},
                namespace=WS_NAMESPACE,
            )
            await self._sio.emit(
                "subscribe_positions",
                {"marketSlugs": self._subscribed_slugs},
                namespace=WS_NAMESPACE,
            )
            await self._sio.emit(
                "subscribe_order_events",
                namespace=WS_NAMESPACE,
            )

    async def subscribe_market(self, slug: str, orderbook_callback: Callable = None):
        if slug not in self._subscribed_slugs:
            self._subscribed_slugs.append(slug)

        if orderbook_callback:
            self._orderbook_callbacks[slug] = orderbook_callback

        if not self._connected:
            await self.connect()

        if self._connected:
            await self._sio.emit(
                "subscribe_market_prices",
                {"marketSlugs": self._subscribed_slugs},
                namespace=WS_NAMESPACE,
            )

    async def subscribe_positions(self, callback: Callable):
        if callback not in self._position_callbacks:
            self._position_callbacks.append(callback)

    async def subscribe_order_events(self, callback: Callable):
        if callback not in self._order_callbacks:
            self._order_callbacks.append(callback)

        if self._connected:
            await self._sio.emit("subscribe_order_events", namespace=WS_NAMESPACE)

    async def disconnect(self):
        if self._sio and self._connected:
            await self._sio.disconnect()
            self._connected = False
