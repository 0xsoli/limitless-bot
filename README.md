# Limitless Trading Bot

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Base](https://img.shields.io/badge/Base-Chain-0052FF?style=for-the-badge&logo=coinbase&logoColor=white)](https://base.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](./LICENSE)

Self-hosted Telegram trading bot for [Limitless Exchange](https://limitless.exchange/?r=SoliTeam) on Base. Browse every market category, place signed CLOB orders, and manage your portfolio — with credentials that never leave your VPS.

Built by [@solixbt](https://x.com/solixbt) for the Limitless community.

---

## Features

- **Full market catalog** — Crypto, Sport, Esports, Finance, Politics, and every other Limitless navigation category
- **Categorized browsing** — Category → optional subcategory filters → paginated market list
- **Buy & sell** — YES / NO for GTC, FAK, and FOK order types
- **EIP-712 order signing** — Orders are built and signed locally with your wallet key per the official Limitless API
- **HMAC API auth** — Every authenticated request uses scoped token HMAC-SHA256 signing
- **Portfolio tools** — Positions, PnL, history, points, cancel-all orders
- **One-line VPS install** — Interactive installer, systemd service, auto-restart

---

## Security

> **Your keys never leave your server.** There is no third-party relay, no external database, and no analytics.

| Item | Detail |
|------|--------|
| Config path | `/etc/limitless-bot/config.json` (`chmod 600`) |
| Private key usage | EIP-712 order signing only (local) |
| API surface | `api.limitless.exchange` and optional `wss://ws.limitless.exchange` |
| Access control | Telegram Chat ID allowlist |

Review the source before running. You control the machine and every credential on it.

---

## Prerequisites

- Ubuntu 20.04+ or Debian 11+ (other Linux distros work with manual install)
- Root access for the systemd installer
- Python 3.9+
- A [Limitless](https://limitless.exchange/?r=SoliTeam) scoped API token with the `trading` scope
- Wallet private key for the same account (EOA trading mode)
- Telegram bot token from [@BotFather](https://t.me/BotFather)
- Your numeric Telegram chat ID from [@userinfobot](https://t.me/userinfobot)

### Trading wallet mode

Self-signed API orders require **EOA** mode on your Limitless profile. If you previously enabled 1-click / smart-wallet trading in the web app, the bot automatically switches the profile to `eoa` on startup via `PUT /profiles`.

### On-chain approvals

Before the first trade on a venue, approve USDC (and Conditional Tokens for sells) to that market’s `venue.exchange` on Base. Approvals are one-time per venue. See the [venue system docs](https://docs.limitless.exchange/developers/venue-system).

---

## Quick install (one line)

```bash
curl -fsSL https://raw.githubusercontent.com/0xsoli/limitless-bot/main/install.sh | sudo bash
```

The installer will:

1. Install system dependencies and create a Python venv  
2. Prompt for API token, Telegram credentials, and wallet private key  
3. Write a locked-down config file  
4. Install and start a `limitless-bot` systemd service  

### Manual install

```bash
git clone https://github.com/0xsoli/limitless-bot.git
cd limitless-bot
sudo bash install.sh
```

### Reconfigure

```bash
sudo bash /opt/limitless-bot/install.sh --reconfigure
```

Or from a fresh clone:

```bash
sudo bash install.sh --reconfigure
```

---

## Credentials

| Field | Description | Source |
|-------|-------------|--------|
| Limitless API Key | Scoped token ID | Profile → API Tokens → Derive |
| Limitless API Secret | Base64 secret (shown once) | Same as above |
| Telegram Bot Token | Bot auth token | @BotFather → `/newbot` |
| Telegram Chat ID | Your numeric user ID | @userinfobot |
| Wallet Private Key | EOA key for EIP-712 signatures | Your wallet (never share this) |

---

## Using the bot

1. Open Telegram and send `/start` to your bot  
2. Tap **Markets** and pick a category (or **All Markets**)  
3. Optionally narrow by subcategory filters (duration, league, game, etc.)  
4. Open a market, then **Buy YES / Buy NO / Sell YES / Sell NO**  
5. Choose **GTC**, **FAK**, or **FOK**, enter size, confirm  

### Order types

| Type | Behavior |
|------|----------|
| **GTC** | Limit order rests until filled or cancelled |
| **FAK** | Fill available liquidity immediately; cancel remainder |
| **FOK** | Fill entirely or reject (market-style spend/size) |

### Commands

| Command | Action |
|---------|--------|
| `/start` | Welcome + main menu |
| `/menu` | Main menu |
| `/market` | Browse markets |
| `/portfolio` | Portfolio overview |
| `/order` | Continue order flow for the selected market |

---

## Service management

```bash
sudo systemctl status limitless-bot
sudo journalctl -u limitless-bot -f
sudo systemctl restart limitless-bot
sudo systemctl stop limitless-bot
sudo cat /var/log/limitless-bot/error.log
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
```

---

## Architecture

```
limitless-bot/
├── bot/
│   ├── main.py              App bootstrap and handler registration
│   ├── config.py            Config load (file + env fallback)
│   ├── limitless_client.py  HMAC client, market APIs, EIP-712 orders
│   ├── websocket_manager.py Optional real-time Socket.IO helper
│   ├── handlers.py          Telegram commands and callbacks
│   ├── keyboards.py         Inline keyboards
│   └── formatters.py        Message formatting
├── run.py                   Entry point
├── requirements.txt
└── install.sh               One-line installer + systemd unit
```

### Order flow (critical path)

1. `GET /profiles/me` → `ownerId`, `rank.feeRateBps`, trading wallet mode  
2. `GET /markets/{slug}` → `tokens.yes` / `tokens.no`, `venue.exchange`, fee flag  
3. Build order amounts (1e6 scale) per GTC / FAK / FOK rules  
4. EIP-712 sign with domain `Limitless CTF Exchange` / chainId `8453` / `verifyingContract = venue.exchange`  
5. `POST /orders` with signed `order`, `ownerId`, `orderType`, `marketSlug`

Authentication on each request:

```
message   = {ISO-8601 timestamp}\n{METHOD}\n{path+query}\n{body}
signature = base64(HMAC-SHA256(base64decode(secret), message))
headers   = lmts-api-key, lmts-timestamp, lmts-signature
```

---

## Disclaimer

This project is **not affiliated** with Limitless Exchange. It is an independent community tool.

**Not financial advice.** Prediction markets involve risk of loss. You are solely responsible for keys, approvals, balances, and orders you submit.

---

## License

MIT
