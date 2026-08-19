import os
import httpx

from broker.acagarwal.baseurl import BASE_URL, INTERACTIVE_URL
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


def _extract_xts_error(response) -> str:
    """Extract human-readable error messages from Symphony XTS responses."""
    try:
        data = response.json()
        # Check for nested validation errors
        errors_list = data.get("result", {}).get("errors", [])
        if errors_list and isinstance(errors_list, list):
            all_msgs = []
            for item in errors_list:
                if isinstance(item, dict) and "messages" in item:
                    all_msgs.extend(item["messages"])
                elif isinstance(item, str):
                    all_msgs.append(item)
            if all_msgs:
                return "; ".join(all_msgs)

        description = data.get("description") or data.get("message")
        if description:
            return description
        return response.text
    except Exception:
        return response.text or f"HTTP {response.status_code}"


def authenticate_broker(request_token=None):
    """
    Authenticates interactive and market data sessions for AC Agarwal (Symphony XTS).
    
    Quirk 1: Interactive login request's "source" field MUST be "WEBAPI" (all caps).
    Quirk 2: Market data login tries multiple endpoint paths with short timeout fallback.
    """
    try:
        client = get_httpx_client()
        BROKER_API_KEY = os.getenv("BROKER_API_KEY")
        BROKER_API_SECRET = os.getenv("BROKER_API_SECRET")

        if not BROKER_API_KEY or not BROKER_API_SECRET:
            return None, None, None, "Missing BROKER_API_KEY or BROKER_API_SECRET in environment"

        # Quirk 1: source must be literal string "WEBAPI" (all caps)
        payload = {
            "appKey": BROKER_API_KEY,
            "secretKey": BROKER_API_SECRET,
            "source": "WEBAPI",
        }

        headers = {"Content-Type": "application/json"}
        session_url = f"{INTERACTIVE_URL}/user/session"

        logger.info(f"[AC Agarwal] Authenticating Interactive API with appKey: {BROKER_API_KEY[:8]}... at {session_url}")
        response = client.post(session_url, json=payload, headers=headers, timeout=10.0)

        if response.status_code == 200:
            result = response.json()
            if result.get("type") == "success":
                token = result["result"]["token"]
                user_id = result["result"].get("userID")
                logger.info(f"[AC Agarwal] Interactive Auth Token obtained successfully (User: {user_id})")

                # Fetch market data feed token (optional enhancement)
                feed_token, feed_user_id, feed_error = get_feed_token()
                if feed_error:
                    logger.warning(f"[AC Agarwal] Market Data Feed Token notice: {feed_error}")

                return token, feed_token, user_id or feed_user_id, None
            else:
                err_msg = result.get("description") or "No access token returned by Symphony XTS"
                return None, None, None, f"Authentication failed: {err_msg}"
        else:
            err_msg = _extract_xts_error(response)
            logger.error(f"[AC Agarwal] Authentication failed (HTTP {response.status_code}): {err_msg}")
            return None, None, None, f"AC Agarwal rejected credentials: {err_msg}"

    except Exception as e:
        logger.exception(f"[AC Agarwal] Exception during authentication: {e}")
        return None, None, None, f"Error connecting to AC Agarwal: {str(e)}"


def get_feed_token():
    """
    Fetches Market Data feed token for AC Agarwal.
    
    Quirk 2: Market-data login needs a fallback across multiple URL paths:
    1. /apimarketdata/auth/login
    2. /marketdata/auth/login
    3. /apibinarymarketdata/auth/login
    First success wins.
    """
    try:
        BROKER_API_KEY_MARKET = os.getenv("BROKER_API_KEY_MARKET") or os.getenv("BROKER_API_KEY")
        BROKER_API_SECRET_MARKET = os.getenv("BROKER_API_SECRET_MARKET") or os.getenv("BROKER_API_SECRET")

        if not BROKER_API_KEY_MARKET or not BROKER_API_SECRET_MARKET:
            return None, None, "Missing Market Data keys"

        # Quirk 1: source must be literal string "WEBAPI" (all caps)
        feed_payload = {
            "appKey": BROKER_API_KEY_MARKET,
            "secretKey": BROKER_API_SECRET_MARKET,
            "source": "WEBAPI",
        }

        feed_headers = {"Content-Type": "application/json"}
        client = get_httpx_client()

        # Candidate paths to attempt for market data login
        candidate_paths = [
            "/apimarketdata/auth/login",
            "/marketdata/auth/login",
            "/apibinarymarketdata/auth/login",
        ]

        last_error = "No market data auth endpoint answered"
        for path in candidate_paths:
            feed_url = f"{BASE_URL}{path}"
            try:
                logger.info(f"[AC Agarwal] Attempting market data login at: {feed_url}")
                feed_response = client.post(feed_url, json=feed_payload, headers=feed_headers, timeout=5.0)

                if feed_response.status_code == 200:
                    feed_result = feed_response.json()
                    if feed_result.get("type") == "success":
                        feed_token = feed_result["result"].get("token")
                        user_id = feed_result["result"].get("userID")
                        logger.info(f"[AC Agarwal] Market Data Feed Token obtained successfully via {path}")
                        return feed_token, user_id, None
                    else:
                        last_error = feed_result.get("description") or "Market data login rejected"
                else:
                    last_error = _extract_xts_error(feed_response)
            except Exception as req_err:
                logger.warning(f"[AC Agarwal] Market data login attempt failed at {path}: {str(req_err)}")
                last_error = str(req_err)

        return None, None, f"Market Data Auth notice: {last_error}"

    except Exception as e:
        return None, None, f"Exception in get_feed_token: {str(e)}"
