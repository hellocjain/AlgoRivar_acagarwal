#!/usr/bin/env bash
# ==============================================================================
# AlgoRivarV2 - Dedicated AC Agarwal (Symphony XTS) Ultra-Fast Ubuntu Installer
# ==============================================================================
set -e

START_TIME=$(date +%s)

GREEN='[0;32m'
CYAN='[0;36m'
YELLOW='[1;33m'
RED='[0;31m'
BOLD='[1m'
NC='[0m'

echo -e "${CYAN}${BOLD}"
echo "======================================================================"
echo "       🚀 AlgoRivarV2 - Dedicated AC Agarwal Automated Installer      "
echo "======================================================================"
echo -e "${NC}"

ACTUAL_USER="${SUDO_USER:-$(whoami)}"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

# Step 0: Ensure swap on low-memory (1GB) VPS to prevent OOM
if [ "$(id -u)" -eq 0 ]; then
  TOTAL_MEM=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo "1024")
  TOTAL_SWAP=$(free -m 2>/dev/null | awk '/^Swap:/{print $2}' || echo "0")
  if [ "$TOTAL_MEM" -lt 2000 ] && [ "$TOTAL_SWAP" -lt 500 ]; then
    echo -e "${YELLOW}[+] Low memory detected (${TOTAL_MEM}MB RAM). Allocating 1GB swap file...${NC}"
    if [ ! -f /swapfile ]; then
      fallocate -l 1G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=1024 2>/dev/null || true
      if [ -f /swapfile ]; then
        chmod 600 /swapfile
        mkswap /swapfile >/dev/null 2>&1 || true
        swapon /swapfile >/dev/null 2>&1 || true
      fi
    fi
  fi
fi

echo -e "${CYAN}[1/5] Checking system prerequisites and firewall...${NC}"
if [ "$(id -u)" -eq 0 ]; then
  export DEBIAN_FRONTEND=noninteractive
  # Wait if cloud-init / unattended-upgrades is holding apt lock
  LOCK_WAIT=0
  while fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/dpkg/lock >/dev/null 2>&1; do
    if [ $LOCK_WAIT -eq 0 ]; then
      echo -e "${YELLOW}[!] Ubuntu background update in progress. Waiting for apt lock to release...${NC}"
    fi
    sleep 2
    LOCK_WAIT=$((LOCK_WAIT + 1))
    if [ $LOCK_WAIT -gt 15 ]; then
      break
    fi
  done
  apt-get update -qq -y > /dev/null 2>&1 || true
  apt-get install -qq -y curl git libevent-dev sqlite3 > /dev/null 2>&1 || true
  ufw allow 5000/tcp > /dev/null 2>&1 || true
  ufw allow 8765/tcp > /dev/null 2>&1 || true
fi

echo -e "
${CYAN}[2/5] Setting up uv Python environment...${NC}"
export PATH="$HOME/.local/bin:/root/.local/bin:/usr/local/bin:$PATH"
if ! command -v uv &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:/root/.local/bin:/usr/local/bin:$PATH"
fi

UV_BIN="$(which uv 2>/dev/null || echo "$HOME/.local/bin/uv")"
if [ ! -x "$UV_BIN" ] && [ -x "/root/.local/bin/uv" ]; then
  UV_BIN="/root/.local/bin/uv"
fi

if [ ! -x "$UV_BIN" ]; then
  echo -e "${YELLOW}[+] Fetching standalone uv binary...${NC}"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh > /dev/null 2>&1 || true
  UV_BIN="$(which uv 2>/dev/null || echo "/usr/local/bin/uv")"
fi

# Ensure Python 3.12 standalone runtime is fetched by uv
"$UV_BIN" python install 3.12 --quiet > /dev/null 2>&1 || true

echo -e "
${CYAN}[3/5] Installing Python dependencies in parallel...${NC}"
"$UV_BIN" sync --quiet

# Pre-create standard directories
mkdir -p db log tmp
chmod 755 db log tmp

echo -e "
${CYAN}[4/5] Auto-detecting Server IP & Generating Secure Configuration...${NC}"
SERVER_IP=$(curl -s --connect-timeout 3 https://api.ipify.org 2>/dev/null || curl -s --connect-timeout 3 https://ifconfig.me 2>/dev/null || curl -s --connect-timeout 3 https://icanhazip.com 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
SERVER_IP=$(echo "$SERVER_IP" | tr -d '[:space:]')
if [ -z "$SERVER_IP" ]; then
  SERVER_IP="127.0.0.1"
fi

echo -e "${GREEN}[+] Detected Server IP: ${SERVER_IP}${NC}"

# Auto-fix / create .env
if [ ! -f ".env" ] || [ ! -s ".env" ] || grep -q "http://:5000" ".env" 2>/dev/null || grep -q "/minute" ".env" 2>/dev/null; then
  echo -e "${GREEN}[+] Generating/Updating production .env configuration...${NC}"
  APP_KEY=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(32))")
  API_KEY_PEPPER=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(32))")
  FERNET_SALT=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(16))")

  cat > .env << ENVEOF
# AlgoRivarV2 Environment Configuration
ENV_CONFIG_VERSION = '1.0.7'

# AC Agarwal Symphony XTS Configuration
VALID_BROKERS = 'acagarwal'
REDIRECT_URL = 'http://${SERVER_IP}:5000/acagarwal/callback'
BROKER_API_KEY = 'YOUR_ACAGARWAL_APP_KEY'
BROKER_API_SECRET = 'YOUR_ACAGARWAL_SECRET_KEY'
BROKER_API_KEY_MARKET = ''
BROKER_API_SECRET_MARKET = ''

# Security Secrets
APP_KEY = '${APP_KEY}'
API_KEY_PEPPER = '${API_KEY_PEPPER}'
FERNET_SALT = '${FERNET_SALT}'

# Database Configuration
DATABASE_URL = 'sqlite:///db/openalgo.db'
LATENCY_DATABASE_URL = 'sqlite:///db/latency.db'
LOGS_DATABASE_URL = 'sqlite:///db/logs.db'
SANDBOX_DATABASE_URL = 'sqlite:///db/sandbox.db'

# Server & Network Settings
FLASK_HOST_IP = '0.0.0.0'
FLASK_PORT = '5000'
FLASK_DEBUG = 'False'
FLASK_ENV = 'production'
NGROK_ALLOW = 'False'
HOST_SERVER = 'http://${SERVER_IP}:5000'

# WebSocket & ZeroMQ Bus
WEBSOCKET_HOST = '0.0.0.0'
WEBSOCKET_PORT = '8765'
WEBSOCKET_URL = 'ws://${SERVER_IP}:8765'
ZMQ_HOST = '127.0.0.1'
ZMQ_PORT = '5555'

# Logging & Limits
LOG_TO_FILE = 'True'
LOG_LEVEL = 'INFO'
LOG_DIR = 'log'
LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
LOG_RETENTION = '14'
LOGIN_RATE_LIMIT_MIN = "5 per minute"
LOGIN_RATE_LIMIT_HOUR = "25 per hour"
RESET_RATE_LIMIT = "15 per hour"
API_RATE_LIMIT = "50 per second"
ORDER_RATE_LIMIT = "10 per second"
SMART_ORDER_RATE_LIMIT = "10 per second"
WEBHOOK_RATE_LIMIT = "100 per minute"
STRATEGY_RATE_LIMIT = "200 per minute"
SESSION_EXPIRY_TIME = '03:00'
DISABLE_SESSION_EXPIRY = 'false'
MASTER_CONTRACT_CUTOFF_TIME = '08:00'
ENVEOF
  chmod 600 .env
  echo -e "${GREEN}[+] .env generated with valid rate limits and security keys!${NC}"
else
  echo -e "${GREEN}[+] Existing .env file detected. Retaining current configuration.${NC}"
fi

# Auto-download master contracts if database table is empty
echo -e "${GREEN}[+] Syncing AC Agarwal Master Contracts in background...${NC}"
"$UV_BIN" run python -c "
from database.token_db import get_token
if not get_token('RELIANCE', 'NSE'):
    from broker.acagarwal.database.master_contract_db import master_contract_download
    master_contract_download()
" > /dev/null 2>&1 &

echo -e "
${CYAN}[5/5] Configuring systemd background auto-start service...${NC}"
if [ "$(id -u)" -eq 0 ]; then
  cat > /etc/systemd/system/algorivar.service << SVCEOF
[Unit]
Description=AlgoRivarV2 Dedicated AC Agarwal Trading Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${UV_BIN} run app.py
Restart=always
RestartSec=3
LimitNOFILE=65536
LimitNPROC=4096
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

  systemctl daemon-reload
  systemctl enable algorivar.service > /dev/null 2>&1 || true
  systemctl restart algorivar.service
  echo -e "${GREEN}[+] systemd service 'algorivar' enabled and active!${NC}"
else
  echo -e "${YELLOW}[!] Non-root user: skipping systemd service registration. You can run manually via: ${UV_BIN} run app.py${NC}"
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo -e "
${GREEN}${BOLD}======================================================================
"
echo -e "       🎉 AlgoRivarV2 Installed & Running in ${ELAPSED} seconds!         "
echo -e "
======================================================================${NC}"
echo -e ""
echo -e "  🌐 ${BOLD}Open your browser and navigate to:${NC}"
echo -e "     ${CYAN}${BOLD}http://${SERVER_IP}:5000${NC}"
echo -e ""
echo -e "  🔑 ${BOLD}First-Time Setup (Zero Terminal Work):${NC}"
echo -e "     1. Create your Admin Password on the web screen"
echo -e "     2. Enter your AC Agarwal Client ID, App Key & Secret Key"
echo -e "     3. Click 'Connect AC Agarwal & Launch' and begin trading!"
echo -e ""
echo -e "  📋 ${BOLD}Service Controls:${NC}"
echo -e "     Status:  systemctl status algorivar"
echo -e "     Logs:    journalctl -u algorivar -f"
echo -e "     Restart: systemctl restart algorivar"
echo -e "======================================================================
"
