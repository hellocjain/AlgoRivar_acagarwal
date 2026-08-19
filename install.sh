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

echo -e ""
echo "======================================================================"
echo "       🚀 AlgoRivarV2 - Dedicated AC Agarwal Automated Installer      "
echo "======================================================================"
echo -e ""

ACTUAL_USER="${SUDO_USER:-$(whoami)}"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

# Step 0: Ensure swap on low-memory (1GB) VPS to prevent OOM
if [ "$(id -u)" -eq 0 ]; then
  TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
  TOTAL_SWAP=$(free -m | awk '/^Swap:/{print $2}')
  if [ "$TOTAL_MEM" -lt 2000 ] && [ "$TOTAL_SWAP" -lt 500 ]; then
    echo -e "[+] Low memory detected (${TOTAL_MEM}MB RAM). Creating 1GB swap file..."
    fallocate -l 1G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=1024 2>/dev/null || true
    if [ -f /swapfile ]; then
      chmod 600 /swapfile
      mkswap /swapfile >/dev/null 2>&1 || true
      swapon /swapfile >/dev/null 2>&1 || true
    fi
  fi
fi

echo -e "[1/5] Checking system prerequisites..."
if [ "$(id -u)" -eq 0 ]; then
  export DEBIAN_FRONTEND=noninteractive
  # Wait if cloud-init / unattended-upgrades is holding apt lock
  LOCK_WAIT=0
  while fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || fuser /var/lib/dpkg/lock >/dev/null 2>&1; do
    if [ $LOCK_WAIT -eq 0 ]; then
      echo -e "[!] Ubuntu background update in progress. Waiting for apt lock to release..."
    fi
    sleep 2
    LOCK_WAIT=$((LOCK_WAIT + 1))
    if [ $LOCK_WAIT -gt 15 ]; then
      break
    fi
  done
  apt-get update -qq -y > /dev/null 2>&1 || true
  apt-get install -qq -y curl git libevent-dev sqlite3 > /dev/null 2>&1 || true
fi

echo -e "
[2/5] Setting up uv Python environment..."
export PATH="$HOME/.local/bin:/root/.local/bin:$PATH"
if ! command -v uv &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh > /dev/null 2>&1 || true
  export PATH="$HOME/.local/bin:/root/.local/bin:$PATH"
fi

UV_BIN="$(which uv || echo "$HOME/.local/bin/uv")"
if [ ! -x "$UV_BIN" ] && [ -x "/root/.local/bin/uv" ]; then
  UV_BIN="/root/.local/bin/uv"
fi

if [ ! -x "$UV_BIN" ]; then
  echo -e "[+] Fetching standalone uv binary..."
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh > /dev/null 2>&1 || true
  UV_BIN="$(which uv || echo "/usr/local/bin/uv")"
fi

# Ensure Python 3.12 standalone runtime is fetched by uv
"$UV_BIN" python install 3.12 --quiet > /dev/null 2>&1 || true

echo -e "
[3/5] Installing Python dependencies in parallel..."
"$UV_BIN" sync --quiet

# Pre-create standard directories
mkdir -p db log tmp
chmod 755 db log tmp

echo -e "
[4/5] Auto-detecting Server IP & Generating Secure Configuration..."
SERVER_IP=$(curl -s --connect-timeout 2 https://api.ipify.org 2>/dev/null || curl -s --connect-timeout 2 https://ifconfig.me 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
SERVER_IP=$(echo "$SERVER_IP" | xargs)

if [ ! -f ".env" ] || [ ! -s ".env" ]; then
  echo -e "[+] Creating secure production .env..."
  APP_KEY=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(32))")
  API_KEY_PEPPER=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(32))")
  FERNET_SALT=$("$UV_BIN" run python -c "import secrets; print(secrets.token_hex(16))")

  cat > .env << EOF
# AlgoRivarV2 Environment Configuration
ENV_CONFIG_VERSION = '1.0.7'

# AC Agarwal Symphony XTS Configuration
VALID_BROKERS = 'acagarwal'
REDIRECT_URL = 'http://:5000/acagarwal/callback'
BROKER_API_KEY = 'YOUR_ACAGARWAL_APP_KEY'
BROKER_API_SECRET = 'YOUR_ACAGARWAL_SECRET_KEY'
BROKER_API_KEY_MARKET = ''
BROKER_API_SECRET_MARKET = ''

# Security Secrets
APP_KEY = ''
API_KEY_PEPPER = ''
FERNET_SALT = ''

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
HOST_SERVER = 'http://:5000'

# WebSocket & ZeroMQ Bus
WEBSOCKET_HOST = '0.0.0.0'
WEBSOCKET_PORT = '8765'
WEBSOCKET_URL = 'ws://:8765'
ZMQ_HOST = '127.0.0.1'
ZMQ_PORT = '5555'

# Logging & Limits
LOG_TO_FILE = 'True'
LOG_LEVEL = 'INFO'
LOG_DIR = 'log'
LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
LOG_RETENTION = '14'
LOGIN_RATE_LIMIT_MIN = '100/minute'
LOGIN_RATE_LIMIT_HOUR = '1000/hour'
API_RATE_LIMIT = '120/minute'
ORDER_RATE_LIMIT = '120/minute'
SMART_ORDER_RATE_LIMIT = '120/minute'
WEBHOOK_RATE_LIMIT = '120/minute'
STRATEGY_RATE_LIMIT = '120/minute'
SESSION_EXPIRY_TIME = '86400'
EOF
  chmod 600 .env
  echo -e "[+] .env generated with encrypted 64-char security keys!"
else
  echo -e "[+] Existing .env file detected. Retaining current configuration."
fi

echo -e "
[5/5] Configuring systemd background auto-start service..."
if [ "$(id -u)" -eq 0 ]; then
  cat > /etc/systemd/system/algorivar.service << EOF
[Unit]
Description=AlgoRivarV2 Dedicated AC Agarwal Trading Engine
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=
ExecStart= run app.py
Restart=always
RestartSec=3
LimitNOFILE=65536
LimitNPROC=4096
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable algorivar.service > /dev/null 2>&1 || true
  systemctl restart algorivar.service
  echo -e "[+] systemd service 'algorivar' enabled and active!"
else
  echo -e "[!] Non-root user: skipping systemd service registration. You can run manually via:  run app.py"
fi

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo -e "
======================================================================"
echo -e "       🎉 AlgoRivarV2 Installed & Running in  seconds!         "
echo -e "======================================================================"
echo -e ""
echo -e "  🌐 Open your browser and navigate to:"
echo -e "     http://:5000"
echo -e ""
echo -e "  🔑 First-Time Setup (Zero Terminal Work):"
echo -e "     1. Create your Admin Password on the web screen"
echo -e "     2. Enter your AC Agarwal Client ID, App Key & Secret Key"
echo -e "     3. Click 'Connect AC Agarwal & Launch' and begin trading!"
echo -e ""
echo -e "  📋 Service Controls:"
echo -e "     Status:  systemctl status algorivar"
echo -e "     Logs:    journalctl -u algorivar -f"
echo -e "     Restart: systemctl restart algorivar"
echo -e "======================================================================"
