# proxies/base.py
from abc import ABC, abstractmethod
import asyncio


class BaseProxy(ABC):
    """
    Abstract base for every proxy.

    Subclasses **must** implement :meth:`start` and :meth:`stop`.

    The optional :attr:`is_ready` / :meth:`wait_until_ready` pair lets
    petals wait until a proxy has finished its startup handshake (e.g.
    MQTT connected, MAVLink heartbeat received) before calling its
    public API.
    """

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    # ── readiness helpers ──────────────────────────────────────────────
    @property
    def is_ready(self) -> bool:
        """Return ``True`` once the proxy is fully usable.

        The default implementation returns ``True`` as soon as
        :meth:`start` has been called.  Subclasses may override this to
        gate on additional conditions (e.g. connection established,
        heartbeat received).
        """
        return getattr(self, "_loop", None) is not None

    async def wait_until_ready(self, timeout: float = 30.0) -> bool:
        """Block (async) until :attr:`is_ready` or *timeout* seconds elapse.

        Returns ``True`` if the proxy became ready, ``False`` on timeout.
        """
        interval = 0.1
        elapsed = 0.0
        while not self.is_ready:
            if elapsed >= timeout:
                return False
            await asyncio.sleep(interval)
            elapsed += interval
        return True