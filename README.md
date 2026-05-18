# Limitless Trading Bot

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Base](https://img.shields.io/badge/Base-Chain-0052FF?style=for-the-badge&logo=coinbase&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Built for](https://img.shields.io/badge/Built%20for-Limitless%20Exchange-9AB83A?style=for-the-badge)

A community-built Telegram trading bot for [Limitless Exchange](https://limitless.exchange/?r=SoliTeam) — the prediction market on Base. Fully self-hosted, your keys never leave your own server.

> Built by [@solixbt](https://x.com/solixbt) for the Limitless community.

---

## Features

- **Step-by-step Trading Flow** — Markets → Timeframe → Token → Order Type → Size → Confirm
- **Three Order Types** — GTC (resting limit), FAK (fill-and-kill), FOK (market order)
- **Real-time Orderbook** — Live updates via WebSocket, no polling
- **Portfolio Dashboard** — Positions, PnL, trade history, and points
- **HMAC-SHA256 Auth** — Every request signed per Limitless API spec
- **Rate Limit Safe** — Enforces 300ms delay and max 2 concurrent requests automatically
- **Auto-reconnect** — WebSocket drops are recovered with full subscription replay
- **Systemd Service** — Runs in the background, restarts on failure, survives reboots

---

## Security

> **Your keys never leave your server.** This bot is fully self-hosted — no third-party service, no cloud relay, no external database.

- All credentials are stored in `/etc/limitless-bot/config.json` on **your own server** with `chmod 600` (readable only by root)
- Your private key is used only to derive your wallet address for profile lookups — it is never transmitted to any external service other than the official Limitless API
- API secrets are stored locally and never logged
- The bot communicates exclusively with `api.limitless.exchange` and `wss://ws.limitless.exchange`
- No analytics, no telemetry, no callbacks — open source and fully auditable

If you are concerned about security, review the source code before running. Every credential stays on the machine you control.

---

## Prerequisites

- Ubuntu 20.04+ or Debian 11+
- Python 3.9+
- Root access (required for systemd service setup)
- A [Limitless Exchange](https://limitless.exchange/?r=SoliTeam) account with a scoped API token (`trading` scope)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/0xsoli/limitless-bot/main/install.sh | sudo bash
```

Or clone and run manually:

```bash
git clone https://github.com/0xsoli/limitless-bot.git
cd limitless-bot
sudo bash install.sh
```

The installer asks for your credentials interactively, saves them securely, and starts the bot as a systemd service.

---

## Required Credentials

| Field | Description | Where to get it |
|---|---|---|
| Limitless API Key | Token ID from API token derivation | [limitless.exchange](https://limitless.exchange) → Profile → API Tokens |
| Limitless API Secret | Secret returned once at token creation | Same as above |
| Telegram Bot Token | Your bot's token from BotFather | [@BotFather](https://t.me/BotFather) → `/newbot` |
| Telegram Chat ID | Your personal numeric chat ID | [@userinfobot](https://t.me/userinfobot) |
| Wallet Private Key | Private key of your trading wallet | Your wallet provider |

---

## Bot Usage

### Step 1 — Start
Send `/start` to your bot. The main menu appears.

### Step 2 — Browse Markets
Tap **📊 Markets** → select a timeframe (**5 Min**, **15 Min**, **Hourly**, **Daily**) → pick any active market from the list.

### Step 3 — View Market
Each market shows live YES / NO prices, volume, liquidity, and an orderbook snapshot. Tap **Buy YES** or **Buy NO** to trade.

### Step 4 — Place an Order
Choose your order type:
- **GTC** — Limit order, rests on the book until filled or cancelled. Enter price and size.
- **FAK** — Fills what it can immediately, cancels the rest. Enter price and size.
- **FOK** — Full fill or nothing, executes at market price. Enter USDC amount to spend.

Review the confirmation screen, then tap **Confirm**.

### Step 5 — Portfolio
Tap **💼 Portfolio** to see your open positions, unrealized PnL, trade history, and accumulated points. Cancel all open orders with one tap.

---

## Service Management

```bash
# Check status
sudo systemctl status limitless-bot

# Live logs
sudo journalctl -u limitless-bot -f

# Restart
sudo systemctl restart limitless-bot

# Stop
sudo systemctl stop limitless-bot

# View error log
sudo cat /var/log/limitless-bot/error.log
```

---

## Reconfigure Credentials

```bash
sudo bash install.sh --reconfigure
```

---

## Uninstall

```bash
sudo systemctl stop limitless-bot
sudo systemctl disable limitless-bot
sudo rm -f /etc/systemd/system/limitless-bot.service
sudo systemctl daemon-reload
sudo rm -rf /opt/limitless-bot
sudo rm -rf /etc/limitless-bot
sudo rm -rf /var/log/limitless-bot
echo "Limitless Bot uninstalled."
```

---

## Architecture

```
limitless-bot/
├── bot/
│   ├── main.py              — App bootstrap and handler registration
│   ├── config.py            — Config loader (file + env var fallback)
│   ├── limitless_client.py  — HMAC-signed API client with rate limiting
│   ├── websocket_manager.py — Socket.IO real-time data manager
│   ├── handlers.py          — All Telegram command and callback handlers
│   ├── keyboards.py         — Inline keyboard layouts
│   └── formatters.py        — Message text formatters
├── run.py                   — Entry point
├── requirements.txt         — Python dependencies
└── install.sh               — One-line installer with systemd setup
```

---

## API Details

All requests to `api.limitless.exchange` use HMAC-SHA256 signing:

```
message   = {ISO-8601 timestamp}\n{METHOD}\n{path+query}\n{body}
signature = base64( HMAC-SHA256( base64decode(secret), message ) )
```

Headers on every authenticated request: `lmts-api-key`, `lmts-timestamp`, `lmts-signature`

Rate limits enforced automatically: max 2 concurrent requests, minimum 300ms between calls, exponential backoff on 429.

---

## Disclaimer

This project is not affiliated with Limitless Exchange. It is an independent, community-built tool created for the Limitless community by [@solixbt](https://x.com/solixbt).

**This is not financial advice.** Trading prediction markets involves risk. Always review orders before confirming. The author is not responsible for any financial losses resulting from use of this software.

---

## License

MIT — free to use, modify, and distribute.
