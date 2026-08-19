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
                        logger.info(f"[AC Agarwal WS] Market Data login successful via {path}")
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

                    ws_url = f"{self.base_url}?token={self.token}&userID={self.user_id}&source=WEBAPI"
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
        def on_market_data(data):
            try:
                if isinstance(data, str):
                    data = json.loads(data)
                if self.on_tick_callback:
                    self.on_tick_callback(data)
            except Exception as e:
                logger.error(f"[AC Agarwal WS] Error processing tick: {e}")

        @self.sio.on("1105-json-full")
        @self.sio.on("1105-json-partial")
        def on_order_update(data):
            try:
                if isinstance(data, str):
                    data = json.loads(data)
                if self.on_order_update_callback:
                    self.on_order_update_callback(data)
            except Exception as e:
                logger.error(f"[AC Agarwal WS] Error processing order update: {e}")

    def subscribe(self, instruments: List[Dict[str, Any]], mode: int = 2) -> bool:
        if not self.connected or not self.token:
            logger.error("[AC Agarwal WS] Cannot subscribe - client disconnected")
            return False

        try:
            candidate_urls = [
                f"{MARKET_DATA_URL}/instruments/subscription",
                f"{BASE_URL}/marketdata/instruments/subscription",
                f"{BASE_URL}/apimarketdata/instruments/subscription",
            ]

            payload = {
                "instruments": instruments,
                "xtsMessageCode": 1502 if mode == 2 else (1505 if mode == 3 else 1501),
            }
            headers = {
                "authorization": self.token,
                "Content-Type": "application/json",
            }

            for u in candidate_urls:
                try:
                    res = requests.post(u, json=payload, headers=headers, timeout=5)
                    if res.status_code == 200:
                        logger.info(f"[AC Agarwal WS] Subscribed successfully at: {u}")
                        return True
                except Exception as e:
                    logger.debug(f"[AC Agarwal WS] Subscription attempt at {u} failed: {e}")

            return False
        except Exception as e:
            logger.error(f"[AC Agarwal WS] Subscription exception: {e}")
            return False
