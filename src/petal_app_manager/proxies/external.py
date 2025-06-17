# petalappmanager/proxies/external.py
from __future__ import annotations
import threading, queue, time
from .base import BaseProxy
from abc import abstractmethod
from collections import defaultdict
from typing import Any, Callable, Dict, List, Mapping, Tuple
from pymavlink import mavutil
# import rospy

class ExternalProxy(BaseProxy):
    """
    Base class for long-running I/O drivers that live on their
    *own* thread and expose two directional buffer maps:

        self._send  : Dict[str, queue.Queue]
        self._recv  : Dict[str, queue.Queue]

    Handlers can be registered so that **every** message arriving
    on _recv[key] is broadcast to the callbacks for that key.
    """

    # ------------ public API ------------ #
    def __init__(self) -> None:
        self._send: Dict[str, "queue.Queue[Any]"] = {}
        self._recv: Dict[str, "queue.Queue[Any]"] = {}
        self._handlers: Dict[str, List[Callable[[Any], None]]] = (
            defaultdict(list)
        )
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def register_handler(self, key: str, fn: Callable[[Any], None]) -> None:
        """Attach a callback for every message on recv-queue *key*."""
        self._handlers[key].append(fn)

    def send(self, key: str, msg: Any) -> None:
        """Put a message onto the send-side buffer *key* (creating it if needed)."""
        self._send.setdefault(key, queue.Queue()).put(msg)

    # ---- life-cycle entry points (used by FastAPI startup/shutdown) ---- #
    async def start(self) -> None:          # called in event-loop thread
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ------------ to be implemented by concrete subclass ------------ #
    @abstractmethod
    def _io_read_once(self) -> list[tuple[str, Any]]:
        """
        Pull *one batch* of data from hardware / middleware.

        Return an iterable of (key, message) that will be
        pushed into _recv and dispatched to handlers.
        """

    @abstractmethod
    def _io_write_once(self, batches: Mapping[str, List[Any]]) -> None:
        """
        Push any pending messages *to* the hardware.
        *batches* maps key -> list[message].
        """

    # ---------------- internal thread loop ---------------- #
    def _run(self) -> None:
        while self._running.is_set():
            # ---- 1. transmit any queued messages ----
            pending: Dict[str, List[Any]] = defaultdict(list)
            for key, q in list(self._send.items()):
                while not q.empty():
                    pending[key].append(q.get_nowait())
            if pending:
                self._io_write_once(pending)

            # ---- 2. poll hardware / middleware ----
            for key, msg in self._io_read_once():
                # fan-out to queue
                self._recv.setdefault(key, queue.Queue()).put(msg)
                # fan-out to handlers
                for cb in self._handlers.get(key, []):
                    try:
                        cb(msg)
                    except Exception as exc:     # never break the loop
                        print(f"[ExternalProxy] handler {cb} raised: {exc}")

            time.sleep(0.01)   # tiny back-off to avoid 100 % CPU


class MavLinkExternalProxy(ExternalProxy):
    """
    Two queues:
        send["mav"]      - outbound messages (mavutil.mavlink.MAVLink_message)
        recv["mav"]      - inbound messages (same type)

    Handlers are registered on key = str(msg.get_msgId())  **or**
    key = msg.get_type().
    """

    def __init__(self, endpoint="udp:127.0.0.1:14551", baud=115200):
        super().__init__()
        self.endpoint = endpoint
        self.baud     = baud
        self.master: mavutil.mavfile | None = None

    async def start(self):
        self.master = mavutil.mavlink_connection(self.endpoint, baud=self.baud)
        await super().start()          # spin up thread **after** connection

    async def stop(self):
        await super().stop()
        if self.master:
            self.master.close()

    # ---------- I/O primitives ---------- #
    def _io_read_once(self) -> List[Tuple[str, Any]]:
        if not self.master:
            return []
        msgs = []
        # non-blocking receive
        while (m := self.master.recv_match(blocking=False)):
            msgs.append(("mav", m))
            # duplicate under two convenient keys for handler matching
            msgs.append((str(m.get_msgId()), m))
            msgs.append((m.get_type(), m))
        return msgs

    def _io_write_once(self, batches):
        if not self.master:
            return
        for msg in batches.get("mav", []):
            try:
                self.master.mav.send(msg)
                print(f"[MavLinkExternalProxy] sent: {msg}")
            except Exception as exc:
                print(f"[MavLinkExternalProxy] send error: {exc}")


class ROS1ExternalProxy(ExternalProxy):
    """
    Four logical queues:
        send["pub/<topic>"]        - outbound ROS messages
        send["svc_client/<srv>"]   - outbound service requests
        recv["sub/<topic>"]        - inbound messages
        recv["svc_server/<srv>"]   - inbound service requests

    Handlers use those exact keys or a wildcard matcher you choose.
    """

    def __init__(self, node_name="petal_ros_proxy"):
        super().__init__()
        self.node_name = node_name
        self._pub_cache: Dict[str, rospy.Publisher] = {}
        self._srv_client_cache: Dict[str, rospy.ServiceProxy] = {}

    async def start(self):
        # rospy.init_node must run once per process; protect with lock
        if not rospy.core.is_initialized():
            rospy.init_node(self.node_name, anonymous=True, disable_signals=True)
        super_ret = await super().start()
        return super_ret

    # ------------ I/O hooks ------------ #
    def _io_read_once(self) -> List[Tuple[str, Any]]:
        """rospy uses callbacks, so inbound data arrive via those
        callbacks and are already queued; nothing to poll here."""
        return []     # nothing extra to read in the main loop

    def _io_write_once(self, batches):
        # ---- publishers ----
        for key, msgs in batches.items():
            if key.startswith("pub/"):
                topic = key[4:]
                pub = self._pub_cache.get(topic)
                if not pub:
                    # We have to import message type dynamically or receive it from user;
                    # placeholder uses rospy.AnyMsg for demo.
                    from rospy.msg import AnyMsg
                    pub = rospy.Publisher(topic, AnyMsg, queue_size=10)
                    self._pub_cache[topic] = pub
                for m in msgs:
                    pub.publish(m)

            elif key.startswith("svc_client/"):
                srv = key[12:]
                proxy = self._srv_client_cache.get(srv)
                if not proxy:
                    # We don't know the concrete service class here; you'd
                    # normally pass it in or discover it.
                    continue
                for req in msgs:
                    try:
                        proxy.call(req)
                    except Exception as exc:
                        print(f"[ROS1ExternalProxy] service error: {exc}")

    # ------------ public helpers ------------ #
    def subscribe(self, topic: str, msg_class, queue_size=10):
        def _cb(msg):
            self._recv.setdefault(f"sub/{topic}", queue.Queue()).put(msg)
            for fn in self._handlers.get(f"sub/{topic}", []):
                fn(msg)
        rospy.Subscriber(topic, msg_class, _cb, queue_size=queue_size)

    def advertise_service(self, srv_name: str, srv_class, handler):
        def _wrapper(req):
            self._recv.setdefault(f"svc_server/{srv_name}", queue.Queue()).put(req)
            for fn in self._handlers.get(f"svc_server/{srv_name}", []):
                fn(req)
            return handler(req)
        rospy.Service(srv_name, srv_class, _wrapper)