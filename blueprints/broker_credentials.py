# blueprints/broker_credentials.py
"""
Broker credentials management API for AlgoRivarV2.
Handles reading and updating AC Agarwal broker credentials in memory and in the .env file.
"""

import os
import re
from functools import wraps

from flask import Blueprint, jsonify, request, session

from utils.logging import get_logger

logger = get_logger(__name__)

broker_credentials_bp = Blueprint("broker_credentials_bp", __name__, url_prefix="/api/broker")


def require_app_user(f):
    """Decorator to ensure user is logged in to the dashboard app."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            return jsonify({"status": "error", "message": "Authentication required. Please log in."}), 401
        return f(*args, **kwargs)

    return decorated_function


def get_env_path():
    """Get the absolute path to the .env file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(base_dir, "..", ".env"))


def read_env_file():
    """Read and parse the .env file into a string."""
    env_path = get_env_path()
    if not os.path.exists(env_path):
        return None, "Environment file not found"

    try:
        with open(env_path, encoding="utf-8") as f:
            return f.read(), None
    except Exception as e:
        logger.exception(f"Error reading .env file: {e}")
        return None, str(e)


def update_env_value(content: str, key: str, value: str) -> str:
    """Update a specific key's value in the .env content."""
    pattern = rf"^({re.escape(key)}\s*=\s*).*$"

    if "'" in value:
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
        new_value = f'"{escaped_value}"'
    else:
        new_value = f"'{value}'"

    replacement = rf"\g<1>{new_value}"
    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)

    if count == 0:
        if not new_content.endswith("\n"):
            new_content += "\n"
        new_content += f"{key} = {new_value}\n"

    return new_content


def get_env_value(key: str) -> str:
    """Get a value from the environment."""
    return os.getenv(key, "")


def mask_secret(value: str, show_chars: int = 4) -> str:
    """Mask a secret value, showing only the first few characters."""
    if not value:
        return ""
    if len(value) <= show_chars:
        return "*" * 8
    return value[:show_chars] + "*" * 8


def get_broker_from_redirect_url(redirect_url: str) -> str:
    """Extract broker name from redirect URL."""
    try:
        match = re.search(r"/([^/]+)/callback$", redirect_url)
        if match:
            return match.group(1).lower()
    except Exception:
        pass
    return "acagarwal"


@broker_credentials_bp.route("/credentials", methods=["GET"])
@require_app_user
def get_credentials():
    """Get current broker credentials (masked)."""
    try:
        broker_api_key = get_env_value("BROKER_API_KEY")
        broker_api_secret = get_env_value("BROKER_API_SECRET")
        broker_api_key_market = get_env_value("BROKER_API_KEY_MARKET")
        broker_api_secret_market = get_env_value("BROKER_API_SECRET_MARKET")
        client_id = get_env_value("CLIENT_ID") or get_env_value("USER_ID")
        redirect_url = get_env_value("REDIRECT_URL") or "http://127.0.0.1:5000/acagarwal/callback"
        valid_brokers = get_env_value("VALID_BROKERS") or "acagarwal"
        ngrok_allow = get_env_value("NGROK_ALLOW")
        host_server = get_env_value("HOST_SERVER")
        websocket_url = get_env_value("WEBSOCKET_URL")

        flask_host = get_env_value("FLASK_HOST_IP") or "0.0.0.0"
        flask_port = get_env_value("FLASK_PORT") or "5000"
        websocket_host = get_env_value("WEBSOCKET_HOST") or "0.0.0.0"
        websocket_port = get_env_value("WEBSOCKET_PORT") or "8765"
        zmq_host = get_env_value("ZMQ_HOST") or "127.0.0.1"
        zmq_port = get_env_value("ZMQ_PORT") or "5555"

        current_broker = "acagarwal"
        brokers_list = ["acagarwal"]

        return jsonify(
            {
                "status": "success",
                "data": {
                    "client_id": client_id,
                    "broker_api_key": mask_secret(broker_api_key, 6),
                    "broker_api_key_raw_length": len(broker_api_key),
                    "broker_api_secret": mask_secret(broker_api_secret, 4),
                    "broker_api_secret_raw_length": len(broker_api_secret),
                    "broker_api_key_market": mask_secret(broker_api_key_market, 6),
                    "broker_api_key_market_raw_length": len(broker_api_key_market),
                    "broker_api_secret_market": mask_secret(broker_api_secret_market, 4),
                    "broker_api_secret_market_raw_length": len(broker_api_secret_market),
                    "redirect_url": redirect_url,
                    "current_broker": current_broker,
                    "valid_brokers": brokers_list,
                    "ngrok_allow": ngrok_allow.upper() == "TRUE",
                    "host_server": host_server,
                    "websocket_url": websocket_url,
                    "server_status": {
                        "flask": {"host": flask_host, "port": flask_port},
                        "websocket": {"host": websocket_host, "port": websocket_port},
                        "zmq": {"host": zmq_host, "port": zmq_port},
                    },
                },
            }
        )
    except Exception as e:
        logger.exception(f"Error getting broker credentials: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@broker_credentials_bp.route("/credentials", methods=["POST"])
@require_app_user
def update_credentials():
    """Update broker credentials in .env file and memory."""
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        client_id = data.get("client_id", "").strip()
        broker_api_key = data.get("broker_api_key", "").strip()
        broker_api_secret = data.get("broker_api_secret", "").strip()
        broker_api_key_market = data.get("broker_api_key_market", "").strip()
        broker_api_secret_market = data.get("broker_api_secret_market", "").strip()
        redirect_url = data.get("redirect_url", "").strip()

        content, error = read_env_file()
        if error:
            content = ""

        updated_fields = []

        if client_id:
            content = update_env_value(content, "CLIENT_ID", client_id)
            content = update_env_value(content, "USER_ID", client_id)
            os.environ["CLIENT_ID"] = client_id
            os.environ["USER_ID"] = client_id
            updated_fields.append("CLIENT_ID")

        if broker_api_key:
            content = update_env_value(content, "BROKER_API_KEY", broker_api_key)
            os.environ["BROKER_API_KEY"] = broker_api_key
            updated_fields.append("BROKER_API_KEY")

        if broker_api_secret:
            content = update_env_value(content, "BROKER_API_SECRET", broker_api_secret)
            os.environ["BROKER_API_SECRET"] = broker_api_secret
            updated_fields.append("BROKER_API_SECRET")

        if broker_api_key_market:
            content = update_env_value(content, "BROKER_API_KEY_MARKET", broker_api_key_market)
            os.environ["BROKER_API_KEY_MARKET"] = broker_api_key_market
            updated_fields.append("BROKER_API_KEY_MARKET")

        if broker_api_secret_market:
            content = update_env_value(content, "BROKER_API_SECRET_MARKET", broker_api_secret_market)
            os.environ["BROKER_API_SECRET_MARKET"] = broker_api_secret_market
            updated_fields.append("BROKER_API_SECRET_MARKET")

        if redirect_url:
            content = update_env_value(content, "REDIRECT_URL", redirect_url)
            os.environ["REDIRECT_URL"] = redirect_url
            updated_fields.append("REDIRECT_URL")

        if not updated_fields:
            return jsonify({"status": "error", "message": "No credentials provided to update"}), 400

        env_path = get_env_path()
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Updated credentials in .env and memory: {', '.join(updated_fields)}")
        except Exception as e:
            logger.exception(f"Error writing .env file: {e}")
            return jsonify({"status": "error", "message": f"Failed to write .env file: {e}"}), 500

        return jsonify(
            {
                "status": "success",
                "message": f"Credentials updated successfully ({', '.join(updated_fields)})",
                "updated_fields": updated_fields,
            }
        )

    except Exception as e:
        logger.exception(f"Error updating broker credentials: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@broker_credentials_bp.route("/direct-connect", methods=["POST"])
def direct_connect():
    """
    Directly save broker credentials, authenticate against AC Agarwal (Symphony XTS),
    and activate user session immediately in 1 click.
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        broker_name = "acagarwal"
        client_id = data.get("client_id", "").strip()
        broker_api_key = data.get("broker_api_key", "").strip()
        broker_api_secret = data.get("broker_api_secret", "").strip()
        broker_api_key_market = data.get("broker_api_key_market", "").strip()
        broker_api_secret_market = data.get("broker_api_secret_market", "").strip()

        if not broker_api_key or not broker_api_secret:
            return jsonify({"status": "error", "message": "Interactive AppKey and SecretKey are required"}), 400

        # 1. Update os.environ in memory
        if client_id:
            os.environ["CLIENT_ID"] = client_id
            os.environ["USER_ID"] = client_id
        os.environ["BROKER_API_KEY"] = broker_api_key
        os.environ["BROKER_API_SECRET"] = broker_api_secret
        if broker_api_key_market:
            os.environ["BROKER_API_KEY_MARKET"] = broker_api_key_market
        if broker_api_secret_market:
            os.environ["BROKER_API_SECRET_MARKET"] = broker_api_secret_market

        port = os.getenv("FLASK_PORT", "5000")
        redirect_url = f"http://127.0.0.1:{port}/acagarwal/callback"
        os.environ["REDIRECT_URL"] = redirect_url
        os.environ["VALID_BROKERS"] = "acagarwal"

        # 2. Persist to .env file
        content, _ = read_env_file()
        if content is None:
            content = ""
        
        if client_id:
            content = update_env_value(content, "CLIENT_ID", client_id)
            content = update_env_value(content, "USER_ID", client_id)
        content = update_env_value(content, "BROKER_API_KEY", broker_api_key)
        content = update_env_value(content, "BROKER_API_SECRET", broker_api_secret)
        if broker_api_key_market:
            content = update_env_value(content, "BROKER_API_KEY_MARKET", broker_api_key_market)
        if broker_api_secret_market:
            content = update_env_value(content, "BROKER_API_SECRET_MARKET", broker_api_secret_market)
        content = update_env_value(content, "REDIRECT_URL", redirect_url)
        content = update_env_value(content, "VALID_BROKERS", "acagarwal")

        env_path = get_env_path()
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"Error saving .env in direct-connect: {e}")

        # 3. Authenticate directly with Symphony XTS
        from broker.acagarwal.api.auth_api import authenticate_broker
        auth_token, feed_token, user_id, error_message = authenticate_broker(broker_name)
        if error_message or not auth_token:
            return jsonify({
                "status": "error",
                "message": f"Broker authentication failed: {error_message or 'Invalid credentials from Symphony XTS'}"
            }), 400

        effective_client_id = client_id or user_id or "ACAGARWAL_USER"

        # 4. Activate User Session and persist tokens & Client ID in auth_db
        from utils.auth_utils import handle_auth_success
        from utils.session import set_session_login_time, get_session_expiry_time
        from flask import current_app as app

        current_user = session.get("user", "admin")
        handle_auth_success(auth_token, current_user, broker_name, feed_token=feed_token, user_id=effective_client_id)

        session["logged_in"] = True
        session["user"] = current_user
        session["user_session_key"] = current_user
        session["broker"] = broker_name
        session["user_id"] = effective_client_id
        if feed_token:
            session["FEED_TOKEN"] = feed_token
        set_session_login_time()
        session.permanent = True
        app.config["PERMANENT_SESSION_LIFETIME"] = get_session_expiry_time()

        logger.info(f"Direct connection successful for AC Agarwal (User: {current_user}, Client ID: {effective_client_id})")

        return jsonify({
            "status": "success",
            "message": f"Connected to AC Agarwal Symphony XTS ({effective_client_id}) successfully!",
            "redirect": "/dashboard"
        })

    except Exception as e:
        logger.exception(f"Error in direct-connect: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@broker_credentials_bp.route("/capabilities", methods=["GET"])
@require_app_user
def get_capabilities():
    """Return broker capabilities from cached plugin.json."""
    from utils.plugin_loader import get_broker_capabilities

    capabilities = get_broker_capabilities("acagarwal")
    if not capabilities:
        return jsonify(
            {
                "status": "success",
                "data": {
                    "broker_name": "AC Agarwal",
                    "broker_type": "IN_stock",
                    "supported_exchanges": ["NSE", "BSE", "NFO", "BFO", "MCX", "NSE_INDEX", "BSE_INDEX"],
                    "leverage_config": False,
                },
            }
        )

    return jsonify({"status": "success", "data": capabilities})
