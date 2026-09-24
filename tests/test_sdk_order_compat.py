import os

import pytest

os.environ.setdefault("TINVEST_TOKEN", "regression-test-tinvest-token")
os.environ.setdefault("GATEWAY_API_KEY", "regression-test-gateway-key")

from omni_cio.adapters import tinvest_order_compat_v1 as sdk_order_compat


class RequestObjectOrders:
    def __init__(self) -> None:
        self.max_lots_request = None
        self.order_price_request = None
        self.orders_request = None

    def get_max_lots(self, request):
        self.max_lots_request = request
        return {"status": "ok"}

    def get_order_price(self, request):
        self.order_price_request = request
        return {"status": "ok"}

    def get_orders(self, request):
        self.orders_request = request
        return {"status": "ok"}


class RequestObjectOperations:
    def __init__(self) -> None:
        self.positions_request = None

    def get_positions(self, request):
        self.positions_request = request
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


def test_sale_adapters_build_only_read_only_request_objects() -> None:
    orders = RequestObjectOrders()
    operations = RequestObjectOperations()
    order_adapter = sdk_order_compat.SaleOrdersServiceRequestAdapter(orders)
    operations_adapter = sdk_order_compat.SaleOperationsServiceRequestAdapter(
        operations
    )

    from t_tech.invest import OrderDirection, Quotation

    quotation = Quotation(units=98, nano=0)
    direction = OrderDirection.ORDER_DIRECTION_SELL
    assert order_adapter.get_max_lots(
        account_id="test-account-3118",
        instrument_id="instrument-uid",
        price=quotation,
    ) == {"status": "ok"}
    assert order_adapter.get_order_price(
        account_id="test-account-3118",
        instrument_id="instrument-uid",
        price=quotation,
        direction=direction,
        quantity=1,
    ) == {"status": "ok"}
    assert order_adapter.get_orders(account_id="test-account-3118") == {"status": "ok"}
    assert operations_adapter.get_positions(account_id="test-account-3118") == {
        "status": "ok"
    }

    assert orders.max_lots_request.account_id == "test-account-3118"
    assert orders.order_price_request.direction == direction
    assert orders.orders_request.account_id == "test-account-3118"
    assert operations.positions_request.account_id == "test-account-3118"


class KeywordOrders:
    def get_max_lots(self, **kwargs):
        return kwargs

    def get_order_price(self, **kwargs):
        return kwargs

    def get_orders(self, **kwargs):
        return kwargs


class KeywordOperations:
    def get_positions(self, **kwargs):
        return kwargs


def test_adapter_retains_keyword_compatibility_for_existing_test_doubles() -> None:
    adapter = sdk_order_compat.OrdersServiceRequestAdapter(KeywordOrders())
    assert adapter.get_max_lots(account_id="a")["account_id"] == "a"
    assert adapter.get_order_price(quantity=3)["quantity"] == 3

    sale_orders = sdk_order_compat.SaleOrdersServiceRequestAdapter(KeywordOrders())
    sale_operations = sdk_order_compat.SaleOperationsServiceRequestAdapter(
        KeywordOperations()
    )
    assert sale_orders.get_orders(account_id="a")["account_id"] == "a"
    assert sale_operations.get_positions(account_id="a")["account_id"] == "a"


class OrdersWithForbiddenMethods(KeywordOrders):
    def post_order(self):
        raise AssertionError("write method must not be forwarded")

    def replace_order(self):
        raise AssertionError("write method must not be forwarded")

    def cancel_order(self):
        raise AssertionError("write method must not be forwarded")


class OperationsWithForbiddenMethods(KeywordOperations):
    def get_withdraw_limits(self):
        raise AssertionError("withdraw-limit method must not be forwarded")

    def get_operations(self):
        raise AssertionError("history method must not be forwarded")


def test_purchase_orders_adapter_remains_narrow() -> None:
    adapter = sdk_order_compat.OrdersServiceRequestAdapter(OrdersWithForbiddenMethods())

    assert sdk_order_compat.ALLOWED_ORDERS_METHODS == frozenset(
        {"get_max_lots", "get_order_price"}
    )
    for method_name in (
        "get_orders",
        "post_order",
        "replace_order",
        "cancel_order",
    ):
        with pytest.raises(AttributeError):
            getattr(adapter, method_name)


def test_sale_adapters_expose_only_explicit_read_methods() -> None:
    orders = sdk_order_compat.SaleOrdersServiceRequestAdapter(
        OrdersWithForbiddenMethods()
    )
    operations = sdk_order_compat.SaleOperationsServiceRequestAdapter(
        OperationsWithForbiddenMethods()
    )

    assert sdk_order_compat.ALLOWED_SALE_ORDERS_METHODS == frozenset(
        {"get_max_lots", "get_order_price", "get_orders"}
    )
    assert sdk_order_compat.ALLOWED_SALE_OPERATIONS_METHODS == frozenset(
        {"get_positions"}
    )
    for method_name in ("post_order", "replace_order", "cancel_order"):
        with pytest.raises(AttributeError):
            getattr(orders, method_name)
    for method_name in ("get_withdraw_limits", "get_operations"):
        with pytest.raises(AttributeError):
            getattr(operations, method_name)


class ClientWithForbiddenServices:
    def __init__(self) -> None:
        self.users = object()
        self.instruments = object()
        self.orders = OrdersWithForbiddenMethods()
        self.operations = OperationsWithForbiddenMethods()
        self.market_data = object()
        self.stop_orders = object()
        self.sandbox = object()


def test_client_views_preserve_separate_minimal_surfaces() -> None:
    client = ClientWithForbiddenServices()
    purchase = sdk_order_compat.ClientView(client)
    sale = sdk_order_compat.SaleClientView(client)

    assert sdk_order_compat.ALLOWED_CLIENT_SERVICES == frozenset(
        {"users", "instruments", "orders"}
    )
    assert sdk_order_compat.ALLOWED_SALE_CLIENT_SERVICES == frozenset(
        {"users", "instruments", "orders", "operations"}
    )
    assert purchase.users is client.users
    assert purchase.instruments is client.instruments
    assert isinstance(purchase.orders, sdk_order_compat.OrdersServiceRequestAdapter)
    with pytest.raises(AttributeError):
        getattr(purchase, "operations")

    assert sale.users is client.users
    assert sale.instruments is client.instruments
    assert isinstance(sale.orders, sdk_order_compat.SaleOrdersServiceRequestAdapter)
    assert isinstance(
        sale.operations,
        sdk_order_compat.SaleOperationsServiceRequestAdapter,
    )

    for view in (purchase, sale):
        for service_name in ("market_data", "stop_orders", "sandbox"):
            with pytest.raises(AttributeError):
                getattr(view, service_name)
