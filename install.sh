#!/usr/bin/env bash
# ==============================================================================
# AlgoRivarV2 - Dedicated AC Agarwal (Symphony XTS) Automated Ubuntu Installer
# ==============================================================================
set -e

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

echo -e "[1/6] Installing system prerequisites..."
if [ "$(id -u)" -eq 0 ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y python3 python3-pip python3-venv git curl build-essential libevent-dev sqlite3 lsof
else
  echo -e "[!] Running without root; assuming packages are already installed."
fi

echo -e "
[2/6] Setting up uv Python package manager..."
if ! command -v uv &> /dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if [ -d "/root/.local/bin" ]; then
    export PATH="/root/.local/bin:$PATH"
  fi
fi

cd "$INSTALL_DIR"
echo -e "
[3/6] Installing Python dependencies with uv..."
uv sync

echo -e "
[4/6] Auto-detecting Server IP & Generating Secure Configuration..."
SERVER_IP=$(curl -s --connect-timeout 2 https://api.ipify.org || hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
SERVER_IP=$(echo "$SERVER_IP" | xargs)

if [ ! -f ".env" ] || [ ! -s ".env" ]; then
  echo -e "[+] Generating new production .env configuration..."
  APP_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  API_KEY_PEPPER=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  FERNET_SALT=$(python3 -c "import secrets; print(secrets.token_hex(16))")

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
  echo -e "[+] .env created with auto-generated 64-char security keys!"
else
  echo -e "[+] Existing .env file found. Preserving current configuration."
fi

echo -e "
[5/6] Configuring systemd background auto-start service..."
if [ "$(id -u)" -eq 0 ]; then
  UV_PATH=$(which uv || echo "/root/.local/bin/uv")
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
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable algorivar.service
  systemctl restart algorivar.service
  echo -e "[+] systemd service 'algorivar' enabled and started successfully!"
else
  echo -e "[!] Non-root user: skipping systemd service registration. You can start the server manually using: uv run app.py"
fi

echo -e "
======================================================================"
echo "       🎉 AlgoRivarV2 Installation Complete & Running!               "
echo "======================================================================"
echo -e ""
echo -e "  🌐 Open your browser and navigate to:"
echo -e "     http://:5000"
echo -e ""
echo -e "  🔑 First-Time Setup Steps:"
echo -e "     1. Create your Admin Password on the web setup screen"
echo -e "     2. Enter your AC Agarwal Client ID, App Key & Secret Key"
echo -e "     3. Click 'Connect AC Agarwal & Launch' and start trading!"
echo -e ""
echo -e "  📋 Service Management Commands:"
echo -e "     Status:  systemctl status algorivar"
echo -e "     Logs:    journalctl -u algorivar -f"
echo -e "     Restart: systemctl restart algorivar"
echo -e "======================================================================"
