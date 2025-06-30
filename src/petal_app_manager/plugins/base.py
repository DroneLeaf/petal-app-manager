from abc import ABC
from typing import Mapping

from petal_app_manager.proxies.base import BaseProxy

class Petal(ABC):
    """
    Petal authors only inherit this; NO FastAPI import, no routers.
    """
    name: str
    version: str

    def __init__(self) -> None:
        self._proxies: Mapping[str, BaseProxy] = {}

    def inject_proxies(self, proxies: Mapping[str, BaseProxy]) -> None:
        for name, proxy in proxies.items():
            if not isinstance(proxy, BaseProxy):          # no tuple needed
                raise TypeError(f"Invalid proxy for {name}: {type(proxy).__name__}")
        self._proxies = proxies