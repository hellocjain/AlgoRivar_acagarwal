import pytest
from utils.plugin_loader import load_broker_capabilities, get_broker_capabilities
from blueprints.broker_credentials import read_env_file, update_env_value, mask_secret

def test_acagarwal_sole_broker_discovery():
    caps = load_broker_capabilities()
    assert 'acagarwal' in caps
    assert list(caps.keys()) == ['acagarwal']
    ac_cap = caps['acagarwal']
    assert ac_cap['broker_type'] == 'IN_stock'
    assert 'NSE' in ac_cap['supported_exchanges']
    assert 'NFO' in ac_cap['supported_exchanges']
    assert 'MCX' in ac_cap['supported_exchanges']

def test_env_updater_functions():
    sample = """BROKER_API_KEY = 'old_key'
BROKER_API_SECRET = 'old_secret'
"""
    updated = update_env_value(sample, 'BROKER_API_KEY', 'new_app_key_123')
    assert "BROKER_API_KEY = 'new_app_key_123'" in updated
    assert "BROKER_API_SECRET = 'old_secret'" in updated

def test_mask_secret():
    assert mask_secret('mysecretpassword', 4) == 'myse********'
    assert mask_secret('short', 4) == 'shor********'
    assert mask_secret('', 4) == ''

def test_acagarwal_auth_api_import():
    from broker.acagarwal.api.auth_api import authenticate_broker, get_feed_token
    assert callable(authenticate_broker)
    assert callable(get_feed_token)

def test_acagarwal_order_api_import():
    from broker.acagarwal.api.order_api import place_order_api, modify_order_api, cancel_order_api
    assert callable(place_order_api)
    assert callable(modify_order_api)
    assert callable(cancel_order_api)

def test_acagarwal_master_contract_import():
    from broker.acagarwal.database.master_contract_db import download_master_contract, master_contract_download
    assert callable(download_master_contract)
    assert callable(master_contract_download)
