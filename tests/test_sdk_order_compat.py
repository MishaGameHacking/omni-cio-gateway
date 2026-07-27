import os

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")

import sdk_order_compat


class RequestObjectOrders:
    def __init__(self) -> None:
        self.max_lots_request = None
        self.order_price_request = None

    def get_max_lots(self, request):
        self.max_lots_request = request
        return {"status": "ok"}

    def get_order_price(self, request):
        self.order_price_request = request
        return {"status": "ok"}


def test_adapter_builds_sdk_request_objects_for_new_orders_methods() -> None:
    orders = RequestObjectOrders()
    adapter = sdk_order_compat.OrdersServiceRequestAdapter(orders)

    from t_tech.invest import OrderDirection, Quotation

    quotation = Quotation(units=271, nano=590_000_000)
    direction = OrderDirection.ORDER_DIRECTION_BUY

    assert adapter.get_max_lots(
        account_id="test-account-3118",
        instrument_id="instrument-uid",
        price=quotation,
    ) == {"status": "ok"}
    assert orders.max_lots_request.account_id == "test-account-3118"
    assert orders.max_lots_request.instrument_id == "instrument-uid"
    assert orders.max_lots_request.price == quotation

    assert adapter.get_order_price(
        account_id="test-account-3118",
        instrument_id="instrument-uid",
        price=quotation,
        direction=direction,
        quantity=3,
    ) == {"status": "ok"}
    assert orders.order_price_request.account_id == "test-account-3118"
    assert orders.order_price_request.instrument_id == "instrument-uid"
    assert orders.order_price_request.price == quotation
    assert orders.order_price_request.direction == direction
    assert orders.order_price_request.quantity == 3


class KeywordOrders:
    def get_max_lots(self, **kwargs):
        return kwargs

    def get_order_price(self, **kwargs):
        return kwargs


def test_adapter_retains_keyword_compatibility_for_existing_test_doubles() -> None:
    adapter = sdk_order_compat.OrdersServiceRequestAdapter(KeywordOrders())
    assert adapter.get_max_lots(account_id="a")["account_id"] == "a"
    assert adapter.get_order_price(quantity=3)["quantity"] == 3
