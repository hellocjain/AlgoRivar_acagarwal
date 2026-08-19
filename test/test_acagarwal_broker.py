import json
import pytest
from utils.plugin_loader import load_broker_capabilities, get_broker_capabilities
from blueprints.broker_credentials import read_env_file, update_env_value, mask_secret

def test_acagarwal_sole_broker_discovery():
    caps = load_broker_capabilities()
    assert "acagarwal" in caps
    assert list(caps.keys()) == ["acagarwal"]
    ac_cap = caps["acagarwal"]
    assert ac_cap["broker_type"] == "IN_stock"
    assert "NSE" in ac_cap["supported_exchanges"]
    assert "NFO" in ac_cap["supported_exchanges"]
    assert "MCX" in ac_cap["supported_exchanges"]

def test_env_updater_functions():
    sample = """BROKER_API_KEY = 'old_key'\nBROKER_API_SECRET = 'old_secret'\n"""
    updated = update_env_value(sample, "BROKER_API_KEY", "new_app_key_123")
    assert "BROKER_API_KEY = 'new_app_key_123'" in updated
    assert "BROKER_API_SECRET = 'old_secret'" in updated

def test_mask_secret():
    assert mask_secret("mysecretpassword", 4) == "myse********"
    assert mask_secret("short", 4) == "shor********"
    assert mask_secret("", 4) == ""

def test_acagarwal_auth_api():
    from broker.acagarwal.api.auth_api import authenticate_broker, get_feed_token, _extract_xts_error
    assert callable(authenticate_broker)
    assert callable(get_feed_token)
    assert callable(_extract_xts_error)

def test_acagarwal_order_api():
    from broker.acagarwal.api.order_api import (
        place_order_api,
        modify_order,
        modify_order_api,
        cancel_order,
        cancel_order_api,
        place_smartorder_api,
        close_all_positions,
        get_order_book,
        get_trade_book,
        get_positions,
        get_holdings,
    )
    assert callable(place_order_api)
    assert callable(modify_order)
    assert callable(modify_order_api)
    assert callable(cancel_order)
    assert callable(cancel_order_api)
    assert callable(place_smartorder_api)
    assert callable(close_all_positions)

def test_acagarwal_data_api():
    from broker.acagarwal.api.data import BrokerData, map_exchange_code
    bd = BrokerData(auth_token="test_token")
    assert hasattr(bd, "get_quotes")
    assert hasattr(bd, "get_depth")
    assert hasattr(bd, "get_history")
    assert map_exchange_code("NSE") == 1
    assert map_exchange_code("NFO") == 2
    assert map_exchange_code("MCX") == 51

def test_acagarwal_funds_api():
    from broker.acagarwal.api.funds import get_margin_data
    assert callable(get_margin_data)
    # Empty token returns empty dict safely
    assert get_margin_data("") == {}

def test_acagarwal_mapping():
    from broker.acagarwal.mapping.transform_data import (
        transform_data,
        transform_modify_order_data,
        map_exchange,
        map_order_type,
        map_product_type,
    )
    from broker.acagarwal.mapping.order_data import (
        transform_order_data,
        calculate_order_statistics,
    )
    assert map_exchange("NSE") == "NSECM"
    assert map_exchange("NFO") == "NSEFO"
    assert map_exchange("MCX") == "MCXFO"
    assert map_order_type("LIMIT") == "LIMIT"
    assert map_order_type("MARKET") == "MARKET"
    assert map_product_type("MIS") == "MIS"
    assert map_product_type("NRML") == "NRML"

    order_in = {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "action": "BUY",
        "pricetype": "LIMIT",
        "quantity": 10,
        "price": 2500.0,
        "product": "MIS",
    }
    transformed = transform_data(order_in, token=2885)
    assert transformed["exchangeInstrumentID"] == 2885
    assert transformed["exchangeSegment"] == "NSECM"
    assert transformed["orderSide"] == "BUY"
    assert transformed["orderQuantity"] == 10

def test_acagarwal_streaming_adapter():
    from broker.acagarwal.streaming.acagarwal_adapter import ACAgarwalWebSocketAdapter, AcagarwalWebSocketAdapter
    adapter = ACAgarwalWebSocketAdapter()
    assert adapter.broker_name == "acagarwal"
    raw_tick = {
        "ExchangeInstrumentID": 2885,
        "ExchangeSegment": 1,
        "LastTradedPrice": 2500.5,
        "Open": 2490.0,
        "High": 2510.0,
        "Low": 2485.0,
        "Close": 2495.0,
        "Volume": 100000,
    }
    parsed = adapter.transform_to_openalgo_format(raw_tick)
    assert parsed["type"] == "quote"
    assert parsed["token"] == "2885"
    assert parsed["exchange"] == "NSE"
    assert parsed["ltp"] == 2500.5

def test_acagarwal_master_contract_import():
    from broker.acagarwal.database.master_contract_db import download_master_contract, master_contract_download
    assert callable(download_master_contract)
    assert callable(master_contract_download)

def test_acagarwal_history_chunking_and_parsing(monkeypatch):
    import pandas as pd
    from broker.acagarwal.api.data import BrokerData
    import httpx

    calls = []
    def mock_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        # Simulate 2 chunks of XTS response
        fake_data = "1724056200|1313.3|1320.0|1310.0|1315.0|50000|0,1724056500|1315.0|1322.0|1314.0|1318.0|60000|0"
        return httpx.Response(200, json={
            "type": "success",
            "code": "s-session-0001",
            "result": {"dataReponse": fake_data}
        })

    # Monkeypatch httpx client get
    from utils import httpx_client
    monkeypatch.setattr(httpx_client.get_httpx_client(), "get", mock_get)

    # Mock token lookup
    from database import token_db
    monkeypatch.setattr(token_db, "get_token", lambda s, e: "2885")

    bd = BrokerData(auth_token="test_auth_token", feed_token="test_feed_token")
    df = bd.get_history("RELIANCE", "NSE", "5m", "2026-08-01", "2026-08-15")

    assert not df.empty
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume", "oi"]
    assert len(df) == 2
    assert df.iloc[0]["open"] == 1313.3
    assert df.iloc[0]["high"] == 1320.0
    assert df.iloc[0]["close"] == 1315.0
    # Verified chunking was triggered across the 15-day span (max 6 days per request)
    assert len(calls) >= 3

def test_acagarwal_quotes_parsing(monkeypatch):
    from broker.acagarwal.api.data import BrokerData
    import httpx

    sample_xts_quotes = {
        "type": "success",
        "code": "s-session-0001",
        "result": {
            "mdp": 1502,
            "quotesList": [{"exchangeSegment": 1, "exchangeInstrumentID": "2885"}],
            "listQuotes": [
                json.dumps({
                    "MessageCode": 1502,
                    "ExchangeSegment": 1,
                    "ExchangeInstrumentID": 2885,
                    "Touchline": {
                        "BidInfo": {"Price": 1313.3, "Size": 58},
                        "AskInfo": {"Price": 1313.5, "Size": 2},
                        "LastTradedPrice": 1313.3,
                        "Open": 1320.3,
                        "High": 1321.6,
                        "Low": 1310.5,
                        "Close": 1322.0,
                        "TotalTradedQuantity": 5384097,
                    }
                })
            ]
        }
    }

    def mock_post(url, json=None, headers=None, timeout=None):
        return httpx.Response(200, json=sample_xts_quotes)

    from utils import httpx_client
    monkeypatch.setattr(httpx_client.get_httpx_client(), "post", mock_post)

    from database import token_db
    monkeypatch.setattr(token_db, "get_token", lambda s, e: "2885")

    bd = BrokerData(auth_token="test_auth_token", feed_token="test_feed_token")
    quote = bd.get_quotes("RELIANCE", "NSE")

    assert quote["symbol"] == "RELIANCE"
    assert quote["exchange"] == "NSE"
    assert quote["ltp"] == 1313.3
    assert quote["open"] == 1320.3
    assert quote["high"] == 1321.6
    assert quote["low"] == 1310.5
    assert quote["close"] == 1322.0
    assert quote["prev_close"] == 1322.0
    assert quote["volume"] == 5384097
    assert quote["bid"] == 1313.3
    assert quote["ask"] == 1313.5

def test_acagarwal_synthetic_limit_market_order(monkeypatch):
    from broker.acagarwal.api.order_api import place_order_api
    import httpx

    placed_payloads = []
    def mock_post(url, headers=None, json=None):
        placed_payloads.append(json)
        return httpx.Response(200, json={
            "type": "success",
            "result": {"AppOrderID": 987654321}
        })

    from utils import httpx_client
    monkeypatch.setattr(httpx_client.get_httpx_client(), "post", mock_post)

    from database import token_db
    monkeypatch.setattr(token_db, "get_token", lambda s, e: "2885")

    # Mock BrokerData.get_quotes to return 1313.30
    from broker.acagarwal.api.data import BrokerData
    monkeypatch.setattr(BrokerData, "get_quotes", lambda self, s, e: {
        "symbol": s, "exchange": e, "ltp": 1313.3, "open": 1320.0, "high": 1325.0, "low": 1310.0, "close": 1315.0, "volume": 1000
    })

    # Test MARKET order conversion to Synthetic LIMIT
    order_data = {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "action": "BUY",
        "pricetype": "MARKET",
        "quantity": 10,
        "product": "MIS",
        "price": 0.0,
    }

    resp, resp_data, orderid = place_order_api(order_data, auth="test_auth")
    assert orderid == 987654321
    assert len(placed_payloads) == 1
    # Check that it got converted to LIMIT with non-zero marketable price
    assert placed_payloads[0]["orderType"] == "LIMIT"
    assert float(placed_payloads[0]["limitPrice"]) > 1300.0

