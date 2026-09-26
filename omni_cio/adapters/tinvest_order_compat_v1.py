from __future__ import annotations

import inspect
from typing import Any, Callable


ALLOWED_ORDERS_METHODS = frozenset(
    {
        "get_max_lots",
        "get_order_price",
    }
)
ALLOWED_CLIENT_SERVICES = frozenset(
    {
        "users",
        "instruments",
        "orders",
    }
)
ALLOWED_SALE_ORDERS_METHODS = frozenset(
    {
        "get_max_lots",
        "get_order_price",
        "get_orders",
    }
)
ALLOWED_SALE_OPERATIONS_METHODS = frozenset({"get_positions"})
ALLOWED_SALE_CLIENT_SERVICES = frozenset(
    {
        "users",
        "instruments",
        "orders",
        "operations",
    }
)


class _RequestAdapter:
    @staticmethod
    def _build_request(request_type: type[Any], values: dict[str, Any]) -> Any:
        request = request_type()
        for field_name, field_value in values.items():
            setattr(request, field_name, field_value)
        return request

    @staticmethod
    def _accepts_keyword_payload(method: Callable[..., Any]) -> bool:
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            return False
        return any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in signature.parameters.values()
        )

    @classmethod
    def _invoke(
        cls,
        service: Any,
        method_name: str,
        request_type: type[Any],
        values: dict[str, Any],
    ) -> Any:
        method = getattr(service, method_name)
        if cls._accepts_keyword_payload(method):
            return method(**values)
        return method(cls._build_request(request_type, values))


class OrdersServiceRequestAdapter(_RequestAdapter):
    """Expose only the two read-only order calculation methods used by purchase preview."""

    __slots__ = ("_orders_service",)

    def __init__(self, orders_service: Any) -> None:
        self._orders_service = orders_service

    @staticmethod
    def _request_types() -> tuple[type[Any], type[Any]]:
        from t_tech.invest import GetMaxLotsRequest, GetOrderPriceRequest

        return GetMaxLotsRequest, GetOrderPriceRequest

    def get_max_lots(self, **kwargs: Any) -> Any:
        get_max_lots_request, _ = self._request_types()
        return self._invoke(
            self._orders_service,
            "get_max_lots",
            get_max_lots_request,
            kwargs,
        )

    def get_order_price(self, **kwargs: Any) -> Any:
        _, get_order_price_request = self._request_types()
        return self._invoke(
            self._orders_service,
            "get_order_price",
            get_order_price_request,
            kwargs,
        )


class SaleOrdersServiceRequestAdapter(_RequestAdapter):
    """Expose the three read-only order methods required by sale-capacity preview."""

    __slots__ = ("_orders_service",)

    def __init__(self, orders_service: Any) -> None:
        self._orders_service = orders_service

    @staticmethod
    def _request_types() -> tuple[type[Any], type[Any], type[Any]]:
        from t_tech.invest import (
            GetMaxLotsRequest,
            GetOrderPriceRequest,
            GetOrdersRequest,
        )

        return GetMaxLotsRequest, GetOrderPriceRequest, GetOrdersRequest

    def get_max_lots(self, **kwargs: Any) -> Any:
        get_max_lots_request, _, _ = self._request_types()
        return self._invoke(
            self._orders_service,
            "get_max_lots",
            get_max_lots_request,
            kwargs,
        )

    def get_order_price(self, **kwargs: Any) -> Any:
        _, get_order_price_request, _ = self._request_types()
        return self._invoke(
            self._orders_service,
            "get_order_price",
            get_order_price_request,
            kwargs,
        )

    def get_orders(self, **kwargs: Any) -> Any:
        _, _, get_orders_request = self._request_types()
        return self._invoke(
            self._orders_service,
            "get_orders",
            get_orders_request,
            kwargs,
        )


class SaleOperationsServiceRequestAdapter(_RequestAdapter):
    """Expose only GetPositions for own-position sale validation."""

    __slots__ = ("_operations_service",)

    def __init__(self, operations_service: Any) -> None:
        self._operations_service = operations_service

    @staticmethod
    def _request_type() -> type[Any]:
        from t_tech.invest import PositionsRequest

        return PositionsRequest

    def get_positions(self, **kwargs: Any) -> Any:
        return self._invoke(
            self._operations_service,
            "get_positions",
            self._request_type(),
            kwargs,
        )


class ClientView:
    """Minimal SDK client surface required by purchase-capacity preview."""

    __slots__ = ("users", "instruments", "orders")

    def __init__(self, client: Any) -> None:
        self.users = client.users
        self.instruments = client.instruments
        self.orders = OrdersServiceRequestAdapter(client.orders)


class SaleClientView:
    """Minimal SDK client surface required by sale-capacity preview."""

    __slots__ = ("users", "instruments", "orders", "operations")

    def __init__(self, client: Any) -> None:
        self.users = client.users
        self.instruments = client.instruments
        self.orders = SaleOrdersServiceRequestAdapter(client.orders)
        self.operations = SaleOperationsServiceRequestAdapter(client.operations)


class ClientContextAdapter:
    def __init__(self, client_context: Any) -> None:
        self._client_context = client_context

    def __enter__(self) -> ClientView:
        return ClientView(self._client_context.__enter__())

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        return self._client_context.__exit__(exc_type, exc, traceback)


class SaleClientContextAdapter:
    def __init__(self, client_context: Any) -> None:
        self._client_context = client_context

    def __enter__(self) -> SaleClientView:
        return SaleClientView(self._client_context.__enter__())

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        return self._client_context.__exit__(exc_type, exc, traceback)


class PurchaseCapacityBaseProxy:
    def __init__(self, base: Any) -> None:
        self._base = base

    def _client_context(self, *args: Any, **kwargs: Any) -> ClientContextAdapter:
        return ClientContextAdapter(self._base.Client(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        if name == "Client":
            return self._client_context
        return getattr(self._base, name)


class SaleCapacityBaseProxy:
    def __init__(self, base: Any) -> None:
        self._base = base

    def _client_context(self, *args: Any, **kwargs: Any) -> SaleClientContextAdapter:
        return SaleClientContextAdapter(self._base.Client(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        if name == "Client":
            return self._client_context
        return getattr(self._base, name)


def with_request_object_orders(base: Any) -> PurchaseCapacityBaseProxy:
    return PurchaseCapacityBaseProxy(base)


def with_sale_request_object_services(base: Any) -> SaleCapacityBaseProxy:
    return SaleCapacityBaseProxy(base)
