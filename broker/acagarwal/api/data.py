# broker/acagarwal/api/data.py

import json
import os
import urllib.parse
from datetime import datetime, timedelta

import pandas as pd
from broker.acagarwal.baseurl import BASE_URL, MARKET_DATA_URL
from database.token_db import get_br_symbol, get_brexchange, get_token, get_tokens_bulk
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)


class BrokerData:
    def __init__(self, auth_token=None, feed_token=None, user_id=None):
        self.auth_token = auth_token
        self.feed_token = feed_token
        self.user_id = user_id

        self.timeframe_map = {
            "1m": "1MIN",
            "5m": "5MIN",
            "15m": "15MIN",
            "30m": "30MIN",
            "60m": "60MIN",
            "D": "1DAY",
        }

    def _get_headers(self):
        if not self.feed_token:
            try:
                from database.auth_db import Auth, decrypt_token
                auth_rec = Auth.query.filter_by(broker="acagarwal").order_by(Auth.id.desc()).first()
                if auth_rec and auth_rec.feed_token:
                    self.feed_token = decrypt_token(auth_rec.feed_token)
            except Exception as db_err:
                logger.debug(f"[AC Agarwal] DB feed token lookup notice: {db_err}")

        if not self.feed_token:
            try:
                from broker.acagarwal.api.auth_api import get_feed_token
                feed_tok, _, _ = get_feed_token()
                if feed_tok:
                    self.feed_token = feed_tok
            except Exception as e:
                logger.debug(f"[AC Agarwal] On-demand feed token fetch failed: {e}")

        token = self.feed_token or self.auth_token or ""
        return {
            "authorization": token,
            "Content-Type": "application/json",
        }

    def get_quotes(self, symbol, exchange):
        try:
            client = get_httpx_client()
            token = get_token(symbol, exchange)

            if not token:
                return {"status": "error", "message": f"Token not found for {symbol}:{exchange}"}

            seg_code = map_exchange_code(exchange)
            token_int = int(token) if str(token).isdigit() else token

            candidate_payloads = [
                {
                    "instruments": [
                        {
                            "exchangeSegment": seg_code,
                            "exchangeInstrumentID": token_int,
                        }
                    ],
                    "xtsMessageCode": 1502,
                    "publishFormat": "JSON",
                },
                {
                    "instruments": [
                        {
                            "exchangeSegment": seg_code,
                            "exchangeInstrumentID": str(token),
                        }
                    ],
                    "xtsMessageCode": 1502,
                    "publishFormat": "JSON",
                },
            ]

            candidate_urls = [
                f"{MARKET_DATA_URL}/instruments/quotes",
                f"{BASE_URL}/marketdata/instruments/quotes",
                f"{BASE_URL}/apimarketdata/instruments/quotes",
            ]

            headers = self._get_headers()
            for u in candidate_urls:
                for payload in candidate_payloads:
                    try:
                        response = client.post(u, json=payload, headers=headers, timeout=5.0)
                        if response.status_code == 200:
                            data = response.json()
                            if data.get("type") == "success":
                                result = data.get("result", {})
                                quotes_list = (
                                    result.get("listQuotes", [])
                                    or result.get("quotesList", [])
                                    or result.get("quotes", [])
                                )
                                if quotes_list:
                                    item = quotes_list[0]
                                    if isinstance(item, str):
                                        try:
                                            item = json.loads(item)
                                        except Exception:
                                            item = {}
                                    touchline = item.get("Touchline") or item.get("touchline") or item
                                    if isinstance(touchline, str):
                                        try:
                                            touchline = json.loads(touchline)
                                        except Exception:
                                            touchline = {}

                                    def _qfloat(val, d=0.0):
                                        try:
                                            return float(val) if val is not None and val != "" else d
                                        except (ValueError, TypeError):
                                            return d

                                    def _qint(val, d=0):
                                        try:
                                            return int(float(val)) if val is not None and val != "" else d
                                        except (ValueError, TypeError):
                                            return d

                                    ltp = _qfloat(
                                        touchline.get("LastTradedPrice")
                                        or touchline.get("lastTradedPrice")
                                        or touchline.get("LTP")
                                        or touchline.get("ltp")
                                        or item.get("LastTradedPrice")
                                        or item.get("LTP")
                                    )
                                    open_p = _qfloat(touchline.get("Open") or touchline.get("open") or item.get("Open"))
                                    high_p = _qfloat(touchline.get("High") or touchline.get("high") or item.get("High"))
                                    low_p = _qfloat(touchline.get("Low") or touchline.get("low") or item.get("Low"))
                                    close_p = _qfloat(touchline.get("Close") or touchline.get("close") or item.get("Close"))
                                    vol = _qint(
                                        touchline.get("TotalTradedQuantity")
                                        or touchline.get("TotalQtyTraded")
                                        or touchline.get("totalQtyTraded")
                                        or touchline.get("Volume")
                                        or touchline.get("volume")
                                        or item.get("TotalTradedQuantity")
                                    )
                                    ask_info = touchline.get("AskInfo") or {}
                                    bid_info = touchline.get("BidInfo") or {}
                                    ask_p = _qfloat(ask_info.get("Price") or ask_info.get("price") or 0.0)
                                    bid_p = _qfloat(bid_info.get("Price") or bid_info.get("price") or 0.0)

                                    return {
                                        "symbol": symbol,
                                        "exchange": exchange,
                                        "ltp": ltp,
                                        "open": open_p,
                                        "high": high_p,
                                        "low": low_p,
                                        "close": close_p,
                                        "prev_close": close_p,
                                        "volume": vol,
                                        "ask": ask_p,
                                        "bid": bid_p,
                                        "oi": 0,
                                        "raw": data,
                                    }
                            return data
                    except Exception as e:
                        logger.debug(f"[AC Agarwal] Quote candidate {u} failed: {e}")

            return {"status": "error", "message": "Failed to fetch quotes from AC Agarwal"}
        except Exception as e:
            logger.error(f"[AC Agarwal] Error fetching quotes: {e}")
            return {"status": "error", "message": str(e)}

    def get_depth(self, symbol, exchange):
        try:
            client = get_httpx_client()
            token = get_token(symbol, exchange)

            url = f"{MARKET_DATA_URL}/instruments/quotes"
            payload = {
                "instruments": [
                    {
                        "exchangeSegment": map_exchange_code(exchange),
                        "exchangeInstrumentID": token,
                    }
                ],
                "xtsMessageCode": 1502,
                "publishFormat": "JSON",
            }

            response = client.post(url, json=payload, headers=self._get_headers())
            if response.status_code == 200:
                return response.json()
            return {"status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            logger.error(f"[AC Agarwal] Error fetching depth: {e}")
            return {"status": "error", "message": str(e)}

    def get_history(self, symbol, exchange, interval, start_date, end_date):
        try:
            client = get_httpx_client()
            token = get_token(symbol, exchange)

            if not token:
                logger.warning(f"[AC Agarwal] Could not find token for {exchange}:{symbol}")
                return pd.DataFrame()

            segment_map = {
                "NSE": "NSECM",
                "BSE": "BSECM",
                "NFO": "NSEFO",
                "BFO": "BSEFO",
                "CDS": "NSECD",
                "MCX": "MCXFO",
                "NSE_INDEX": "NSECM",
                "BSE_INDEX": "BSECM",
            }
            exchange_segment = segment_map.get(exchange, "NSECM")

            norm_interval = str(interval).lower().strip()
            compression_map = {
                "1s": "1",
                "1m": "60",
                "1": "60",
                "2m": "120",
                "2": "120",
                "3m": "180",
                "3": "180",
                "5m": "300",
                "5": "300",
                "10m": "600",
                "10": "600",
                "15m": "900",
                "15": "900",
                "30m": "1800",
                "30": "1800",
                "60m": "3600",
                "60": "3600",
                "1h": "3600",
                "d": "D",
                "1d": "D",
                "day": "D",
            }
            compression_value = compression_map.get(norm_interval, "300")

            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            from_date = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            to_date = end_dt.replace(hour=23, minute=59, second=59, microsecond=0)

            dfs = []
            current_start = from_date

            candidate_urls = [
                f"{MARKET_DATA_URL}/instruments/ohlc",
                f"{BASE_URL}/marketdata/instruments/ohlc",
                f"{BASE_URL}/apimarketdata/instruments/ohlc",
            ]
            headers = self._get_headers()

            # Symphony XTS allows max 6-7 days per OHLC request
            while current_start <= to_date:
                current_end = min(current_start + timedelta(days=6), to_date)
                from_str = current_start.strftime("%b %d %Y %H%M%S")
                to_str = current_end.strftime("%b %d %Y %H%M%S")

                params = {
                    "exchangeSegment": exchange_segment,
                    "exchangeInstrumentID": str(token),
                    "startTime": from_str,
                    "endTime": to_str,
                    "compressionValue": compression_value,
                }

                chunk_df = None
                candidate_segments = [exchange_segment, map_exchange_code(exchange), str(map_exchange_code(exchange))]
                for u in candidate_urls:
                    for seg in candidate_segments:
                        params = {
                            "exchangeSegment": seg,
                            "exchangeInstrumentID": str(token),
                            "startTime": from_str,
                            "endTime": to_str,
                            "compressionValue": compression_value,
                        }
                        try:
                            response = client.get(u, params=params, headers=headers, timeout=5.0)
                            if response.status_code == 200:
                                res = response.json()
                                if res.get("type") == "success":
                                    result = res.get("result", {})
                                    raw_data = (
                                        result.get("dataReponse")
                                        or result.get("dataResponse")
                                        or result.get("data", "")
                                    )
                                    if isinstance(raw_data, str) and raw_data.strip():
                                        rows = raw_data.strip().split(",")
                                        parsed_bars = []
                                        for row in rows:
                                            fields = row.split("|")
                                            if len(fields) >= 6:
                                                try:
                                                    parsed_bars.append(
                                                        {
                                                            "timestamp": int(float(fields[0])),
                                                            "open": float(fields[1]),
                                                            "high": float(fields[2]),
                                                            "low": float(fields[3]),
                                                            "close": float(fields[4]),
                                                            "volume": int(float(fields[5])),
                                                            "oi": int(float(fields[6])) if len(fields) > 6 and str(fields[6]).replace('.', '', 1).isdigit() else 0,
                                                        }
                                                    )
                                                except (ValueError, IndexError):
                                                    continue
                                        if parsed_bars:
                                            chunk_df = pd.DataFrame(parsed_bars)
                                            break
                                    elif isinstance(raw_data, list) and len(raw_data) > 0:
                                        chunk_df = pd.DataFrame(raw_data)
                                        break
                        except Exception as e:
                            logger.debug(f"[AC Agarwal] History candidate {u} with seg {seg} failed: {e}")
                    if chunk_df is not None and not chunk_df.empty:
                        break

                if chunk_df is not None and not chunk_df.empty:
                    dfs.append(chunk_df)

                current_start = current_end + timedelta(days=1)

            if dfs:
                combined_df = pd.concat(dfs, ignore_index=True)
                if "timestamp" in combined_df.columns:
                    combined_df = combined_df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
                    numeric_cols = ["open", "high", "low", "close", "volume"]
                    for col in numeric_cols:
                        if col in combined_df.columns:
                            combined_df[col] = pd.to_numeric(combined_df[col], errors="coerce").fillna(0.0)
                return combined_df

            # Fallback if OHLC query returned empty: generate baseline candle from live touchline quote
            try:
                quote = self.get_quotes(symbol, exchange)
                if isinstance(quote, dict) and float(quote.get("ltp") or 0) > 0:
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    today_candle = {
                        "timestamp": int(today.timestamp()),
                        "open": float(quote.get("open") or quote.get("ltp")),
                        "high": float(quote.get("high") or quote.get("ltp")),
                        "low": float(quote.get("low") or quote.get("ltp")),
                        "close": float(quote.get("ltp")),
                        "volume": int(quote.get("volume") or 0),
                        "oi": 0,
                    }
                    return pd.DataFrame([today_candle])
            except Exception as q_err:
                logger.debug(f"[AC Agarwal] Fallback quote candle generation notice: {q_err}")

            return pd.DataFrame()
        except Exception as e:
            logger.error(f"[AC Agarwal] Error fetching history: {e}")
            return pd.DataFrame()


def map_exchange_code(exchange):
    mapping = {
        "NSE": 1,
        "NFO": 2,
        "CDS": 3,
        "BSE": 11,
        "BFO": 12,
        "MCX": 51,
    }
    return mapping.get(exchange, 1)
