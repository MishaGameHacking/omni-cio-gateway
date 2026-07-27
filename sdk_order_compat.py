from __future__ import annotations

import inspect
from typing import Any, Callable


class OrdersServiceRequestAdapter:
    """Adapt newer request-object SDK methods to the gateway's keyword calls."""

    def __init__(self, orders_service: Any) -> None:
        self._orders_service = orders_service

    @staticmethod
    def _request_types() -> tuple[type[Any], type[Any]]:
        from t_tech.invest import GetMaxLotsRequest, GetOrderPriceRequest

        return GetMaxLotsRequest, GetOrderPriceRequest

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

    def get_max_lots(self, **kwargs: Any) -> Any:
        method = self._orders_service.get_max_lots
        if self._accepts_keyword_payload(method):
            return method(**kwargs)
        get_max_lots_request, _ = self._request_types()
        return method(self._build_request(get_max_lots_request, kwargs))

    def get_order_price(self, **kwargs: Any) -> Any:
        method = self._orders_service.get_order_price
        if self._accepts_keyword_payload(method):
            return method(**kwargs)
        _, get_order_price_request = self._request_types()
        return method(self._build_request(get_order_price_request, kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._orders_service, name)


class ClientView:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.orders = OrdersServiceRequestAdapter(client.orders)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


class ClientContextAdapter:
    def __init__(self, client_context: Any) -> None:
        self._client_context = client_context

    def __enter__(self) -> ClientView:
        return ClientView(self._client_context.__enter__())

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        return self._client_context.__exit__(exc_type, exc, traceback)


class PurchaseCapacityBaseProxy:
    def __init__(self, base: Any) -> None:
        self._base = base

    def Client(self, *args: Any, **kwargs: Any) -> ClientContextAdapter:
        return ClientContextAdapter(self._base.Client(*args, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)


def with_request_object_orders(base: Any) -> PurchaseCapacityBaseProxy:
    return PurchaseCapacityBaseProxy(base)
