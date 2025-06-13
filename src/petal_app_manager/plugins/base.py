from abc import ABC
from typing import Mapping, Any

class Petal(ABC):
    """
    Petal authors only inherit this; NO FastAPI import, no routers.
    """
    name: str
    version: str

    def inject_proxies(self, proxies: Mapping[str, Any]):
        """PetalAppManager calls this once with live proxies."""
        self._proxies = proxies