# broker/acagarwal/streaming/acagarwal_adapter.py

import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional

from broker.acagarwal.streaming.acagarwal_mapping import ACAgarwalCapabilityRegistry, ACAgarwalExchangeMapper
from broker.acagarwal.streaming.acagarwal_websocket import ACAgarwalWebSocketClient
from database.auth_db import get_auth_token, get_feed_token
from database.token_db import get_symbol
from websocket_proxy.base_adapter import BaseBrokerWebSocketAdapter

logger = logging.getLogger(__name__)


class ACAgarwalWebSocketAdapter(BaseBrokerWebSocketAdapter):
    """
    AC Agarwal (Symphony XTS) specific implementation of the WebSocket adapter.
    """

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("acagarwal_websocket")
        self.ws_client = None
        self.user_id = None
        self.broker_name = "acagarwal"
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.running = False
        self.lock = threading.Lock()

    def initialize(
        self, broker_name: str, user_id: str, auth_data: dict[str, str] | None = None
    ) -> None:
        self.user_id = user_id
        self.broker_name = broker_name

        if not auth_data:
            auth_token = get_auth_token(user_id, bypass_cache=True)
            feed_token = get_feed_token(user_id)

            api_key = os.getenv("BROKER_API_KEY_MARKET") or os.getenv("BROKER_API_KEY")
            api_secret = os.getenv("BROKER_API_SECRET_MARKET") or os.getenv("BROKER_API_SECRET")

            if not api_key or not api_secret:
                raise ValueError("Missing AC Agarwal API credentials in environment variables")

        self.ws_client = ACAgarwalWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            user_id=user_id,
        )

        self.ws_client.on_tick_callback = self._handle_tick
        self.ws_client.on_order_update_callback = self._handle_order_update
        self.running = True

    def connect(self) -> dict:
        if self.ws_client:
            success = self.ws_client.connect()
            if success:
                return {"status": "success"}
            return {"status": "error", "message": "Failed to connect to AC Agarwal WebSocket"}
        return {"status": "error", "message": "WebSocket client not initialized"}

    def disconnect(self) -> None:
        if self.ws_client:
            self.ws_client.disconnect()
        self.running = False

    def subscribe(self, symbol: str, exchange: str, mode: int = 2, depth_level: int = 5) -> dict:
        """
        Subscribe to market data for a symbol.
        """
        try:
            from database.token_db import get_token
            token = get_token(symbol, exchange)
            if not token:
                self.logger.warning(f"[AC Agarwal WS] Token not found for {exchange}:{symbol}")
                return {"status": "error", "message": f"Token not found for {exchange}:{symbol}"}

            exch_code = ACAgarwalExchangeMapper.get_exchange_type(exchange)
            instruments = [{
                "exchangeSegment": exch_code,
                "exchangeInstrumentID": int(token) if str(token).isdigit() else token,
            }]

            self.logger.info(f"[AC Agarwal WS] Subscribing {exchange}:{symbol} (token={token}, seg={exch_code}) mode={mode}")
            if self.ws_client:
                success = self.ws_client.subscribe(instruments, mode=mode)
                return {"status": "success" if success else "error"}
            return {"status": "error", "message": "WebSocket client not initialized"}
        except Exception as e:
            self.logger.error(f"[AC Agarwal WS] Subscribe error: {e}")
            return {"status": "error", "message": str(e)}

    def unsubscribe(self, symbol: str, exchange: str, mode: int = 2) -> dict:
        """
        Unsubscribe from market data for a symbol.
        """
        try:
            from database.token_db import get_token
            token = get_token(symbol, exchange)
            if not token:
                return {"status": "error", "message": f"Token not found for {exchange}:{symbol}"}

            if self.ws_client:
                return {"status": "success"}
            return {"status": "error", "message": "WebSocket client not initialized"}
        except Exception as e:
            self.logger.error(f"[AC Agarwal WS] Unsubscribe error: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_tick(self, raw_tick: dict):
        try:
            self.logger.debug(f"[AC Agarwal WS] Received raw tick: {raw_tick}")
            parsed = self.transform_to_openalgo_format(raw_tick)
            if parsed and parsed.get("symbol"):
                exchange = parsed.get("exchange", "NSE")
                symbol = parsed.get("symbol")

                # Publish to all standard modes for server.py zmq_listener:
                # Format expected by server.py: {EXCHANGE}_{SYMBOL}_{MODE}
                topic_ltp = f"{exchange}_{symbol}_LTP"
                topic_quote = f"{exchange}_{symbol}_QUOTE"
                topic_depth = f"{exchange}_{symbol}_DEPTH"

                self.logger.info(f"[AC Agarwal WS] Publishing tick for {exchange}:{symbol} -> LTP: {parsed.get('ltp')}")
                self.publish_market_data(topic_ltp, parsed)
                self.publish_market_data(topic_quote, parsed)
                self.publish_market_data(topic_depth, parsed)
        except Exception as e:
            self.logger.error(f"[AC Agarwal WS] Tick handler error: {e}")

    def _handle_order_update(self, raw_update: dict):
        try:
            if isinstance(raw_update, str):
                raw_update = json.loads(raw_update)
            # Route order update if needed
            self.logger.info(f"[AC Agarwal WS] Received order update: {raw_update}")
        except Exception as e:
            self.logger.error(f"[AC Agarwal WS] Order update handler error: {e}")

    def transform_to_openalgo_format(self, raw_data: Any) -> Dict[str, Any]:
        try:
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception:
                    return {}

            if not isinstance(raw_data, dict):
                return {}

            def _to_float(val, default=0.0):
                if val is None or val == "":
                    return default
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return default

            def _to_int(val, default=0):
                if val is None or val == "":
                    return default
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return default

            # In Symphony XTS, touchline details can be nested in Touchline or flat
            touchline = raw_data.get("Touchline") or raw_data.get("touchline") or raw_data
            if isinstance(touchline, str):
                try:
                    touchline = json.loads(touchline)
                except Exception:
                    touchline = {}

            token = str(
                raw_data.get("ExchangeInstrumentID")
                or raw_data.get("exchangeInstrumentID")
                or raw_data.get("Token")
                or raw_data.get("token")
                or ""
            )
            exch_code = raw_data.get("ExchangeSegment") or raw_data.get("exchangeSegment") or 1
            exchange = ACAgarwalExchangeMapper.get_openalgo_exchange(exch_code)
            symbol = get_symbol(token, exchange) or token

            ltp = _to_float(
                touchline.get("LastTradedPrice")
                or touchline.get("lastTradedPrice")
                or touchline.get("LTP")
                or touchline.get("ltp")
                or raw_data.get("LastTradedPrice")
                or raw_data.get("LTP")
                or 0.0
            )
            open_p = _to_float(touchline.get("Open") or touchline.get("open") or raw_data.get("Open"))
            high_p = _to_float(touchline.get("High") or touchline.get("high") or raw_data.get("High"))
            low_p = _to_float(touchline.get("Low") or touchline.get("low") or raw_data.get("Low"))
            close_p = _to_float(touchline.get("Close") or touchline.get("close") or raw_data.get("Close"))
            vol = _to_int(
                touchline.get("TotalQtyTraded")
                or touchline.get("totalQtyTraded")
                or touchline.get("Volume")
                or touchline.get("volume")
                or raw_data.get("TotalQtyTraded")
            )

            # Extract depth book if present in Symphony XTS payload
            bids_raw = raw_data.get("Bids") or raw_data.get("bids") or raw_data.get("Buy") or touchline.get("Bids") or []
            asks_raw = raw_data.get("Asks") or raw_data.get("asks") or raw_data.get("Sell") or touchline.get("Asks") or []

            buy_depth = []
            if isinstance(bids_raw, list):
                for b in bids_raw:
                    if isinstance(b, dict):
                        p = _to_float(b.get("Price") or b.get("price") or b.get("Rate"))
                        q = _to_int(b.get("Size") or b.get("quantity") or b.get("Qty"))
                        buy_depth.append({"price": p, "quantity": q})

            sell_depth = []
            if isinstance(asks_raw, list):
                for a in asks_raw:
                    if isinstance(a, dict):
                        p = _to_float(a.get("Price") or a.get("price") or a.get("Rate"))
                        q = _to_int(a.get("Size") or a.get("quantity") or a.get("Qty"))
                        sell_depth.append({"price": p, "quantity": q})

            result_dict = {
                "type": "quote",
                "symbol": symbol,
                "token": token,
                "exchange": exchange,
                "ltp": ltp,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
                "raw": raw_data,
            }

            if buy_depth or sell_depth:
                result_dict["depth"] = {
                    "buy": buy_depth,
                    "sell": sell_depth,
                }

            return result_dict
        except Exception as e:
            self.logger.error(f"[AC Agarwal WS] Error transforming data: {e}")
            return {}


# Class name alias expected by broker_factory capitalization logic
AcagarwalWebSocketAdapter = ACAgarwalWebSocketAdapter
