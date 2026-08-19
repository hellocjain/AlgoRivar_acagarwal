# broker/acagarwal/streaming/acagarwal_websocket.py

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import requests
import socketio
from broker.acagarwal.baseurl import BASE_URL, INTERACTIVE_URL, MARKET_DATA_URL

logger = logging.getLogger(__name__)


class ACAgarwalWebSocketClient:
    """
    AC Agarwal (Symphony XTS) Socket.IO client for market data streaming.
    """

    BASE_URL = BASE_URL
    SOCKET_PATH = "/apimarketdata/socket.io"
    API_BASE_URL = f"{MARKET_DATA_URL}/instruments/subscription"

    SUBSCRIBE_ACTION = 1
    UNSUBSCRIBE_ACTION = 0

    LTP_MODE = 1
    QUOTE_MODE = 2
    DEPTH_MODE = 3

    def __init__(self, api_key: str, api_secret: str, user_id: str, base_url: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.base_url = base_url or self.BASE_URL

        self.token = None
        self.sio = None
        self.connected = False
        self.subscribed_instruments = {}

        self.on_connect_callback = None
        self.on_disconnect_callback = None
        self.on_tick_callback = None
        self.on_order_update_callback = None
        self.on_error_callback = None

        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.running = False
        self.lock = threading.Lock()

    def _login(self) -> bool:
        candidate_paths = [
            "/apimarketdata/auth/login",
            "/marketdata/auth/login",
            "/apibinarymarketdata/auth/login",
        ]
        payload = {
            "appKey": self.api_key,
            "secretKey": self.api_secret,
            "source": "WEBAPI",
        }
        headers = {"Content-Type": "application/json"}

        for path in candidate_paths:
            try:
                url = f"{self.base_url}{path}"
                logger.info(f"[AC Agarwal WS] Logging in to Market Data API at: {url}")
                response = requests.post(url, json=payload, headers=headers, timeout=5)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("type") == "success":
                        self.token = data["result"].get("token")
                        actual_uid = data["result"].get("userID")
                        if actual_uid:
                            self.user_id = actual_uid
                        logger.info(f"[AC Agarwal WS] Market Data login successful via {path} (userID: {self.user_id})")
                        return True
            except Exception as e:
                logger.debug(f"[AC Agarwal WS] Login attempt failed at {path}: {e}")

        logger.error("[AC Agarwal WS] Market data login failed across all endpoints")
        return False

    def connect(self) -> bool:
        with self.lock:
            if self.connected:
                return True

            if not self.token:
                if not self._login():
                    return False

            candidate_socket_paths = [
                "/apimarketdata/socket.io",
                "/marketdata/socket.io",
                "/socket.io",
            ]

            for spath in candidate_socket_paths:
                try:
                    self.sio = socketio.Client(
                        reconnection=True,
                        reconnection_attempts=self.max_reconnect_attempts,
                        reconnection_delay=self.reconnect_delay,
                        reconnection_delay_max=self.max_reconnect_delay,
                        logger=False,
                        engineio_logger=False,
                    )

                    self._register_events()

                    ws_url = (
                        f"{self.base_url}/?token={self.token}&userID={self.user_id}"
                        f"&publishFormat=JSON&broadcastMode=FULL"
                    )
                    logger.info(f"[AC Agarwal WS] Connecting Socket.IO client at {spath}...")
                    self.sio.connect(ws_url, socketio_path=spath, transports=["websocket"])

                    self.running = True
                    return True
                except Exception as e:
                    logger.debug(f"[AC Agarwal WS] Socket.IO connection attempt failed at {spath}: {e}")

            self.connected = False
            return False

    def disconnect(self):
        with self.lock:
            self.running = False
            if self.sio and self.connected:
                try:
                    self.sio.disconnect()
                except Exception as e:
                    logger.error(f"[AC Agarwal WS] Error disconnecting: {e}")
            self.connected = False

    def _register_events(self):
        @self.sio.on("connect")
        def on_connect():
            logger.info("[AC Agarwal WS] Socket.IO connected")
            self.connected = True
            if self.on_connect_callback:
                self.on_connect_callback()

        @self.sio.on("disconnect")
        def on_disconnect():
            logger.info("[AC Agarwal WS] Socket.IO disconnected")
            self.connected = False
            if self.on_disconnect_callback:
                self.on_disconnect_callback()

        @self.sio.on("1501-json-full")
        @self.sio.on("1501-json-partial")
        @self.sio.on("1502-json-full")
        @self.sio.on("1502-json-partial")
        @self.sio.on("1505-json-full")
        @self.sio.on("1505-json-partial")
        @self.sio.on("1507-json-full")
        @self.sio.on("1510-json-full")
        @self.sio.on("1512-json-full")
        @self.sio.on("touchline")
        @self.sio.on("ltp")
        def on_market_data(data, *args):
            try:
                if not data and args:
                    data = args[0]
                if not data:
                    return

                if isinstance(data, bytes):
                    try:
                        data = data.decode("utf-8")
                    except Exception:
                        pass

                if isinstance(data, str):
                    s = data.strip()
                    if s.startswith("{") or s.startswith("["):
                        try:
                            data = json.loads(s)
                        except Exception:
                            return
                    else:
                        return

                if isinstance(data, dict):
                    if self.on_tick_callback:
                        self.on_tick_callback(data)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, str) and (item.strip().startswith("{") or item.strip().startswith("[")):
                            try:
                                item = json.loads(item.strip())
                            except Exception:
                                continue
                        if isinstance(item, dict) and self.on_tick_callback:
                            self.on_tick_callback(item)
            except Exception as e:
                logger.error(f"[AC Agarwal WS] Error processing tick: {e}")

        @self.sio.on("1105-json-full")
        @self.sio.on("1105-json-partial")
        def on_order_update(data, *args):
            try:
                if not data and args:
                    data = args[0]
                if not data:
                    return

                if isinstance(data, bytes):
                    try:
                        data = data.decode("utf-8")
                    except Exception:
                        pass

                if isinstance(data, str):
                    s = data.strip()
                    if s.startswith("{") or s.startswith("["):
                        try:
                            data = json.loads(s)
                        except Exception:
                            return
                    else:
                        return

                if self.on_order_update_callback:
                    self.on_order_update_callback(data)
            except Exception as e:
                logger.error(f"[AC Agarwal WS] Error processing order update: {e}")

        @self.sio.on("*")
        def catch_all(event, data=None, *args):
            try:
                if event in ("connect", "disconnect"):
                    return
                if not data and args:
                    data = args[0]
                if not data:
                    return

                if isinstance(data, bytes):
                    try:
                        data = data.decode("utf-8")
                    except Exception:
                        pass

                if isinstance(data, str):
                    s = data.strip()
                    if s.startswith("{") or s.startswith("["):
                        try:
                            data = json.loads(s)
                        except Exception:
                            return
                    else:
                        return

                if isinstance(data, dict) and str(data.get("code", "")).startswith("s-socket"):
                    logger.info(f"[AC Agarwal WS] Control handshake: {data.get('description')}")
                    return

                logger.info(f"[AC Agarwal WS] Event '{event}' payload: {data}")

                if "1105" in str(event) or "order" in str(event).lower():
                    if self.on_order_update_callback:
                        self.on_order_update_callback(data)
                else:
                    if isinstance(data, dict):
                        if self.on_tick_callback:
                            self.on_tick_callback(data)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, str) and (item.strip().startswith("{") or item.strip().startswith("[")):
                                try:
                                    item = json.loads(item.strip())
                                except Exception:
                                    continue
                            if isinstance(item, dict) and self.on_tick_callback:
                                self.on_tick_callback(item)
            except Exception as e:
                logger.error(f"[AC Agarwal WS] Error in catch-all event '{event}': {e}")

    def subscribe(self, instruments: List[Dict[str, Any]], mode: int = 2) -> bool:
        if not self.connected or not self.token:
            logger.error("[AC Agarwal WS] Cannot subscribe - client disconnected")
            return False

        try:
            mode_to_xts_code = {
                1: 1512,  # LTP
                2: 1501,  # Quote
                3: 1502,  # Depth
            }
            xts_code = mode_to_xts_code.get(mode, 1502 if mode == 3 else 1501)

            clean_instruments = []
            for inst in instruments:
                clean_instruments.append({
                    "exchangeSegment": int(inst.get("exchangeSegment", 1)),
                    "exchangeInstrumentID": str(inst.get("exchangeInstrumentID", "")),
                })

            sub_url = f"{MARKET_DATA_URL}/instruments/subscription"
            payload = {
                "instruments": clean_instruments,
                "xtsMessageCode": xts_code,
            }
            headers = {
                "Authorization": self.token,
                "Content-Type": "application/json",
            }

            logger.info(f"[AC Agarwal WS] Subscribing code {xts_code} at {sub_url} for {clean_instruments}")
            res = requests.post(sub_url, json=payload, headers=headers, timeout=5)

            if res.status_code == 200:
                result = res.json()
                logger.info(f"[AC Agarwal WS] Subscription response: {result}")
                if result.get("type") == "success" and "result" in result:
                    list_quotes = result["result"].get("listQuotes", [])
                    for quote_str in list_quotes:
                        try:
                            quote_data = json.loads(quote_str) if isinstance(quote_str, str) else quote_str
                            if self.on_tick_callback and isinstance(quote_data, dict):
                                self.on_tick_callback(quote_data)
                        except Exception as e:
                            logger.error(f"[AC Agarwal WS] Error parsing initial quote: {e}")
                return True
            else:
                logger.error(f"[AC Agarwal WS] Subscription failed ({res.status_code}): {res.text}")
                return False

        except Exception as e:
            logger.error(f"[AC Agarwal WS] Subscription exception: {e}")
            return False
