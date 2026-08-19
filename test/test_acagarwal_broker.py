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
