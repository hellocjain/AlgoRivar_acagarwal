# broker/acagarwal/mapping/transform_data.py

import os
from database.token_db import get_br_symbol
from utils.logging import get_logger

logger = get_logger(__name__)


def transform_data(data, token):
    """
    Transforms standard OpenAlgo API request into AC Agarwal (Symphony XTS) payload.
    Hardened with battle-tested Symphony XTS requirements.
    """
    token_val = None
    if token is not None:
        try:
            token_val = int(str(token).strip())
        except ValueError:
            token_val = str(token).strip()

    transformed = {
        "exchangeSegment": map_exchange(data["exchange"]),
        "exchangeInstrumentID": token_val,
        "productType": map_product_type(data["product"]),
        "orderType": map_order_type(data["pricetype"]),
        "orderSide": data["action"].upper(),
        "timeInForce": "DAY",
        "disclosedQuantity": 0,
        "orderQuantity": int(data["quantity"]),
        "limitPrice": float(data.get("price", 0.0)),
        "stopPrice": float(data.get("trigger_price", 0.0)),
        "apiOrderSource": "WEBAPI",
        "orderUniqueIdentifier": data.get("order_ref", "algorivar"),
    }
    client_id = data.get("client_id") or data.get("clientID") or os.getenv("CLIENT_ID")
    if client_id and client_id != "MASTER":
        transformed["clientID"] = str(client_id).strip()

    logger.info(f"[AC Agarwal] Transformed order payload: {transformed}")
    return transformed


def transform_modify_order_data(data, token):
    """
    Transforms OpenAlgo order modification payload into Symphony XTS structure.
    """
    return {
        "appOrderID": str(data["orderid"]),
        "modifiedProductType": map_product_type(data["product"]),
        "modifiedOrderType": map_order_type(data["pricetype"]),
        "modifiedOrderQuantity": int(data["quantity"]),
        "modifiedDisclosedQuantity": str(data.get("disclosed_quantity", "0")),
        "modifiedLimitPrice": str(data["price"]),
        "modifiedStopPrice": str(data.get("trigger_price", "0")),
        "modifiedTimeInForce": "DAY",
        "orderUniqueIdentifier": "algorivar",
    }


def map_exchange(exchange):
    exchange_mapping = {
        "NSE": "NSECM",
        "BSE": "BSECM",
        "MCX": "MCXFO",
        "NFO": "NSEFO",
        "BFO": "BSEFO",
        "CDS": "NSECD",
    }
    return exchange_mapping.get(exchange, exchange)


def map_order_type(pricetype):
    order_type_mapping = {
        "MARKET": "MARKET",
        "LIMIT": "LIMIT",
        "SL": "STOPLIMIT",
        "SL-M": "STOPMARKET",
    }
    return order_type_mapping.get(pricetype, "MARKET")


def map_product_type(product):
    product_mapping = {
        "MIS": "MIS",
        "NRML": "NRML",
        "CNC": "CNC",
    }
    return product_mapping.get(product, "NRML")


def reverse_map_product_type(product_type):
    reverse_mapping = {
        "MIS": "MIS",
        "NRML": "NRML",
        "CNC": "CNC",
    }
    return reverse_mapping.get(product_type, product_type)
