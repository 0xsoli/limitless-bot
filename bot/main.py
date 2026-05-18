import asyncio
import logging
import os
import sys

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

from .handlers import (
    start_handler,
    menu_handler,
    market_handler,
    order_handler,
    portfolio_handler,
    callback_handler,
    message_handler,
)
from .config import load_config
from .limitless_client import LimitlessClient
from .websocket_manager import WebSocketManager

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
logger = logging.getLogger("limitless-bot")


async def post_init(application: Application) -> None:
    config = application.bot_data["config"]
    client = LimitlessClient(config["api_key"], config["api_secret"])
    ws_manager = WebSocketManager(config["api_key"], application.bot)
    application.bot_data["client"] = client
    application.bot_data["ws_manager"] = ws_manager
    application.bot_data["active_markets"] = {}
    application.bot_data["user_sessions"] = {}
    logger.info("Bot initialized successfully")


async def post_shutdown(application: Application) -> None:
    ws_manager = application.bot_data.get("ws_manager")
    if ws_manager:
        await ws_manager.disconnect()
    logger.info("Bot shut down cleanly")


def main():
    config = load_config()

    app = (
        Application.builder()
        .token(config["bot_token"])
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.bot_data["config"] = config

    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("menu", menu_handler))
    app.add_handler(CommandHandler("portfolio", portfolio_handler))
    app.add_handler(CommandHandler("market", market_handler))
    app.add_handler(CommandHandler("order", order_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Starting Limitless Trading Bot...")
    app.run_polling(drop_pending_updates=True)
