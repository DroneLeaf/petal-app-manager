from abc import ABC
from typing import Mapping

from petal_app_manager.proxies.base import Proxy
from petal_app_manager.proxies.localdb import LocalDBProxy
from petal_app_manager.proxies.mavlink import MavLinkProxy


class Petal(ABC):
    """
    Petal authors only inherit this; NO FastAPI import, no routers.
    """
    name: str
    version: str

    def inject_proxies(self, proxies: Mapping[str, Proxy | MavLinkProxy | LocalDBProxy]) -> None:
        """PetalAppManager calls this once with live proxies."""
        self._proxies = proxies