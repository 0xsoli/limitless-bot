#!/usr/bin/env bash

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="/opt/limitless-bot"
CONFIG_DIR="/etc/limitless-bot"
CONFIG_FILE="$CONFIG_DIR/config.json"
SERVICE_NAME="limitless-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
LOG_DIR="/var/log/limitless-bot"
REPO_URL="https://github.com/0xsoli/limitless-bot"

print_header() {
    echo ""
    echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║    Limitless Trading Bot Installer by solixbt   ║${NC}"
    echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "\n${BLUE}${BOLD}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✔ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✖ $1${NC}"
}

prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local secret="${3:-false}"
    local value=""

    while [[ -z "$value" ]]; do
        if [[ "$secret" == "true" ]]; then
            read -rsp "  ${prompt}: " value </dev/tty
            echo ""
        else
            read -rp "  ${prompt}: " value </dev/tty
        fi
        if [[ -z "$value" ]]; then
            print_warning "This field is required. Please enter a value."
        fi
    done

    printf -v "$var_name" '%s' "$value"
}

prompt_with_default() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"
    local value=""

    read -rp "  ${prompt} [${default}]: " value </dev/tty
    value="${value:-$default}"
    printf -v "$var_name" '%s' "$value"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This installer must be run as root."
        echo "  Run: sudo bash install.sh"
        exit 1
    fi
}

install_system_dependencies() {
    print_step "Installing system dependencies"

    if ! command -v apt-get &>/dev/null; then
        print_error "This installer supports Ubuntu/Debian only (apt-get not found)."
        exit 1
    fi

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        git \
        curl \
        ca-certificates

    if ! command -v python3 &>/dev/null; then
        print_error "Python 3 installation failed."
        exit 1
    fi

    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)"; then
        python3_version=$(python3 --version 2>&1 | awk '{print $2}')
        print_error "Python 3.9+ is required. Found: $python3_version"
        exit 1
    fi

    python3_version=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "System dependencies installed (Python $python3_version)"
}

collect_config() {
    print_step "Configuration Setup"
    echo ""
    echo -e "  ${BOLD}Please provide your credentials:${NC}"
    echo -e "  ${YELLOW}All fields are required. Values will be stored securely in $CONFIG_FILE${NC}"
    echo ""

    prompt_input "Limitless API Key (Token ID)" LIMITLESS_API_KEY
    prompt_input "Limitless API Secret" LIMITLESS_API_SECRET true
    prompt_input "Telegram Bot Token" TELEGRAM_BOT_TOKEN true
    prompt_input "Telegram Chat ID" TELEGRAM_CHAT_ID
    prompt_input "Wallet Private Key (0x...)" WALLET_PRIVATE_KEY true

    echo ""
    echo -e "  ${BOLD}Review your configuration:${NC}"
    echo -e "  API Key:       ${LIMITLESS_API_KEY:0:8}…"
    echo -e "  Bot Token:     ${TELEGRAM_BOT_TOKEN:0:8}…"
    echo -e "  Chat ID:       ${TELEGRAM_CHAT_ID}"
    echo -e "  Private Key:   ${WALLET_PRIVATE_KEY:0:6}…"
    echo ""

    read -rp "  Proceed with this configuration? [Y/n]: " confirm </dev/tty
    confirm="${confirm:-Y}"
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        print_warning "Installation cancelled."
        exit 0
    fi
}

install_bot() {
    print_step "Installing bot files"

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ -f "$SCRIPT_DIR/run.py" ]]; then
        cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
        print_success "Files copied from local source"
    elif [[ -d "$INSTALL_DIR/.git" ]]; then
        print_warning "Updating existing repository..."
        git -C "$INSTALL_DIR" pull --ff-only --quiet
        print_success "Repository updated"
    else
        print_warning "Cloning from repository..."
        rm -rf "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR" --quiet
        print_success "Repository cloned"
    fi

    print_step "Creating Python virtual environment"
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip setuptools wheel

    if ! "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"; then
        print_error "Failed to install Python dependencies."
        echo "  Try manually: $INSTALL_DIR/venv/bin/pip install -r $INSTALL_DIR/requirements.txt"
        exit 1
    fi

    print_success "Python dependencies installed"
}

write_config() {
    print_step "Writing configuration"

    cat > "$CONFIG_FILE" <<EOF
{
  "api_key": "${LIMITLESS_API_KEY}",
  "api_secret": "${LIMITLESS_API_SECRET}",
  "bot_token": "${TELEGRAM_BOT_TOKEN}",
  "chat_id": "${TELEGRAM_CHAT_ID}",
  "wallet_private_key": "${WALLET_PRIVATE_KEY}"
}
EOF

    chmod 600 "$CONFIG_FILE"
    chmod 700 "$CONFIG_DIR"
    print_success "Config written to $CONFIG_FILE (permissions: 600)"
}

create_service() {
    print_step "Creating systemd service"

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Limitless Exchange Trading Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python3 ${INSTALL_DIR}/run.py
Restart=on-failure
RestartSec=10
StandardOutput=append:${LOG_DIR}/bot.log
StandardError=append:${LOG_DIR}/error.log
Environment=CONFIG_PATH=${CONFIG_FILE}

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" --quiet
    print_success "Systemd service created and enabled"
}

start_service() {
    print_step "Starting the bot"
    systemctl start "$SERVICE_NAME"
    sleep 2

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "Bot is running!"
    else
        print_error "Bot failed to start. Check logs:"
        echo "  journalctl -u $SERVICE_NAME -n 30"
        echo "  cat $LOG_DIR/error.log"
    fi
}

print_completion() {
    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║            Installation Complete! 🎉             ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Useful commands:${NC}"
    echo -e "  ${CYAN}systemctl status $SERVICE_NAME${NC}      — Check status"
    echo -e "  ${CYAN}systemctl restart $SERVICE_NAME${NC}     — Restart bot"
    echo -e "  ${CYAN}systemctl stop $SERVICE_NAME${NC}        — Stop bot"
    echo -e "  ${CYAN}journalctl -u $SERVICE_NAME -f${NC}      — Live logs"
    echo -e "  ${CYAN}cat $LOG_DIR/error.log${NC}  — Error log"
    echo ""
    echo -e "  ${BOLD}Config file:${NC}  $CONFIG_FILE"
    echo -e "  ${BOLD}Install dir:${NC}  $INSTALL_DIR"
    echo ""
    echo -e "  ${YELLOW}Open Telegram and send /start to your bot!${NC}"
    echo ""
}

reconfigure() {
    print_step "Reconfiguring existing installation"
    collect_config
    write_config
    systemctl restart "$SERVICE_NAME"
    print_success "Configuration updated and bot restarted"
    exit 0
}

print_header
check_root

if [[ "${1:-}" == "--reconfigure" ]]; then
    reconfigure
fi

if [[ -f "$CONFIG_FILE" ]]; then
    echo -e "  ${YELLOW}Existing installation detected.${NC}"
    read -rp "  Reinstall and reconfigure? [y/N]: " reinstall </dev/tty
    if [[ ! "$reinstall" =~ ^[Yy]$ ]]; then
        print_warning "Installation cancelled."
        exit 0
    fi
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
fi

install_system_dependencies
collect_config
install_bot
write_config
create_service
start_service
print_completion
