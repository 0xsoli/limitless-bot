import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/etc/limitless-bot/config.json"))


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info("Config loaded from %s", CONFIG_PATH)
        return _normalize(config)

    config = {
        "api_key": os.environ.get("LIMITLESS_API_KEY", ""),
        "api_secret": os.environ.get("LIMITLESS_API_SECRET", ""),
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "wallet_private_key": os.environ.get("WALLET_PRIVATE_KEY", ""),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        raise RuntimeError(f"Missing required config keys: {missing}")

    return _normalize(config)


def _normalize(config: dict) -> dict:
    pk = (config.get("wallet_private_key") or "").strip()
    if pk and not pk.startswith("0x"):
        pk = "0x" + pk
    config["wallet_private_key"] = pk
    config["api_key"] = str(config.get("api_key") or "").strip()
    config["api_secret"] = str(config.get("api_secret") or "").strip()
    config["bot_token"] = str(config.get("bot_token") or "").strip()
    config["chat_id"] = str(config.get("chat_id") or "").strip()
    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)
    logger.info("Config saved to %s", CONFIG_PATH)
