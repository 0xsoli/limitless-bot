import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "/etc/limitless-bot/config.json"))


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        logger.info(f"Config loaded from {CONFIG_PATH}")
        return config

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

    return config


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)
    logger.info(f"Config saved to {CONFIG_PATH}")
