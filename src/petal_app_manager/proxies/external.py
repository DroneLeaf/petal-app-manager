"""
petalappmanager.proxies.external
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Thread-based proxies for long-running I/O back-ends (MAVLink, ROS 1, …).

Key changes vs. the first draft:
--------------------------------
* All per-key buffers are now :class:`collections.deque` with ``maxlen``.
  New data silently overwrites the oldest entry → bounded memory.
* Public API (``send``, ``register_handler``) is unchanged for petals.
* Docstrings preserved / expanded for clarity.
"""

from __future__ import annotations

import threading
import time
from abc import abstractmethod
from collections import defaultdict, deque
from typing import Any, Callable, Deque, Dict, List, Mapping, Tuple
import logging

from .base import BaseProxy
from pymavlink import mavutil, mavftp
# import rospy   # ← uncomment in ROS-enabled environments


# ──────────────────────────────────────────────────────────────────────────────
class ExternalProxy(BaseProxy):
    """
    Base class for I/O drivers that must *poll* or *listen* continuously.

    A dedicated thread calls :py:meth:`_io_read_once` / :py:meth:`_io_write_once`
    in a tight loop while the FastAPI event-loop thread stays unblocked.

    *   **Send buffers**  - ``self._send[key]``  (deque, newest → right side)
    *   **Recv buffers**  - ``self._recv[key]``  (deque, newest → right side)

    When a message arrives on ``_recv[key]`` every registered handler for
    that *key* is invoked in the worker thread.  Handlers should be fast or
    off-load work to an `asyncio` task via `loop.call_soon_threadsafe`.
    """

    # ──────────────────────────────────────────────────────── public helpers ──
    def __init__(self, maxlen: int = 10) -> None:
        """
        Parameters
        ----------
        maxlen :
            Maximum number of messages kept *per key* in both send/recv maps.
            A value of 0 or ``None`` means *unbounded* (not recommended).
        """
        self._maxlen = maxlen
        self._send: Dict[str, Deque[Any]] = {}
        self._recv: Dict[str, Deque[Any]] = {}
        self._handlers: Dict[str, List[Callable[[Any], None]]] = (
            defaultdict(list)
        )
        self._running = threading.Event()
        self._thread: threading.Thread | None = None

    def register_handler(self, key: str, fn: Callable[[Any], None]) -> None:
        """
        Attach *fn* so it fires for **every** message appended to ``_recv[key]``.

        The callback executes in the proxy thread; never block for long.
        """
        self._handlers[key].append(fn)

    def unregister_handler(self, key: str, fn: Callable[[Any], None]) -> None:
        """
        Remove the callback *fn* from the broadcast list attached to *key*.

        If *fn* was not registered, the call is silently ignored.
        When the last callback for *key* is removed, the key itself is pruned
        to keep the dict size small.
        """
        callbacks = self._handlers.get(key)
        if not callbacks:
            return  # nothing registered under that key

        try:
            callbacks.remove(fn)
        except ValueError:
            self._log.warning(
                "Tried to unregister handler %s for key '%s' but it was not found.",
                fn, key
            )
            return  # fn was not in the list; ignore

        if not callbacks:              # list now empty → delete key
            del self._handlers[key]

    def send(self, key: str, msg: Any) -> None:
        """
        Enqueue *msg* for transmission.  The newest message is kept if the
        buffer is already full.
        """
        self._send.setdefault(key, deque(maxlen=self._maxlen)).append(msg)

    # ───────────────────────────────────────────── FastAPI life-cycle hooks ──
    async def start(self) -> None:
        """Create the worker thread and begin polling/writing."""
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        """Ask the worker to exit and join it (best-effort, 5 s timeout)."""
        self._running.clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ─────────────────────────────────────────────── subclass responsibilities ─
    @abstractmethod
    def _io_read_once(self) -> List[Tuple[str, Any]]:
        """
        Retrieve **zero or more** `(key, message)` tuples from the device /
        middleware *without blocking*.

        Returning an empty list is perfectly fine.
        """

    @abstractmethod
    def _io_write_once(self, batches: Mapping[str, List[Any]]) -> None:
        """
        Push pending outbound messages to the device / middleware.

        ``batches`` maps *key* → list of messages drained from ``_send[key]``.
        """

    # ─────────────────────────────────────────── internal worker main-loop ──
    def _run(self) -> None:
        """Worker thread body - drains send queues, polls recv, fires handlers."""
        while self._running.is_set():
            # 1 - DRIVE OUTBOUND
            pending: Dict[str, List[Any]] = defaultdict(list)
            for key, dq in list(self._send.items()):
                while dq:
                    pending[key].append(dq.popleft())
            if pending:
                self._io_write_once(pending)

            # 2 - POLL INBOUND
            for key, msg in self._io_read_once():
                dq = self._recv.setdefault(key, deque(maxlen=self._maxlen))
                dq.append(msg)
                # broadcast
                for cb in self._handlers.get(key, []):
                    try:
                        cb(msg)
                    except Exception as exc:          # never kill the loop
                        self._log.error(
                            "[ExternalProxy] handler %s raised: %s",
                            cb, exc
                        )

            time.sleep(0.01)   # 10 ms - prevents 100 % CPU spin


# ──────────────────────────────────────────────────────────────────────────────
class MavLinkExternalProxy(ExternalProxy):
    """
    Threaded MAVLink driver using :pymod:`pymavlink`.

    Buffers used
    ------------
    * ``send["mav"]``                      - outbound :class:`MAVLink_message`
    * ``recv["mav"]``                      - any inbound message
    * ``recv[str(msg.get_msgId())]``       - by numeric ID
    * ``recv[msg.get_type()]``             - by string type
    """

    def __init__(
        self,
        endpoint: str = "udp:127.0.0.1:14551",
        baud: int = 115200,
        maxlen: int = 200,
    ):
        super().__init__(maxlen=maxlen)
        self.endpoint = endpoint
        self.baud = baud
        self.master: mavutil.mavfile | None = None
        self._log = logging.getLogger("MavLinkParser")

    # ------------------------ life-cycle --------------------- #
    async def start(self):
        """Open the MAVLink connection then launch the worker thread."""
        self.master = mavutil.mavlink_connection(self.endpoint, baud=self.baud)
        while not self.master.wait_heartbeat(timeout=5):
            self._log.warning(
                "No heartbeat from MAVLink endpoint %s at %d baud",
                self.endpoint, self.baud
            )
        self._log.info("Heartbeat from sys %s, comp %s",
                        self.master.target_system, self.master.target_component)
            
        self.ftp = mavftp.MAVFTP(
            self.master, self.master.target_system, self.master.target_component
        )

        await super().start()

    async def stop(self):
        """Stop the worker and close the link."""
        await super().stop()
        if self.master:
            self.master.close()

    # ------------------- I/O primitives --------------------- #
    def _io_read_once(self) -> List[Tuple[str, Any]]:
        """Non-blocking read of all waiting MAVLink messages."""
        if not self.master:
            return []
        out: List[Tuple[str, Any]] = []
        while (msg := self.master.recv_match(blocking=False)):
            out.append(("mav", msg))
            out.append((str(msg.get_msgId()), msg))
            out.append((msg.get_type(), msg))
        return out

    def _io_write_once(self, batches):
        """Send queued MAVLink messages."""
        if not self.master:
            return
        for key, msgs in batches.items():
            for msg in msgs:
                try:
                    self.master.mav.send(msg)
                except Exception as exc:
                    self._log.error(
                        "Failed to send MAVLink message %s: %s",
                        key, exc
                    )

    # ------------------- helpers exposed to petals --------- #
    def build_req_msg_long(self, message_id: int) -> mavutil.mavlink.MAVLink_command_long_message:
        """
        Build a MAVLink command to request a specific message type.

        Parameters
        ----------
        message_id : int
            The numeric ID of the MAVLink message to request.

        Returns
        -------
        mavutil.mavlink.MAVLink_command_long_message
            The MAVLink command message to request the specified message.
        """
                                
        cmd = self.master.mav.command_long_encode(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE, 
            0,                # confirmation
            float(message_id), # param1: Message ID to be streamed
            0, 
            0, 
            0, 
            0, 
            0, 
            0
        )
        return cmd

    def build_req_msg_log_request(self, message_id: int) -> mavutil.mavlink.MAVLink_log_request_list_message:
        """
        Build a MAVLink command to request a specific log message.

        Parameters
        ----------
        message_id : int
            The numeric ID of the log message to request.

        Returns
        -------
        mavutil.mavlink.MAVLink_log_request_list_message
            The MAVLink command message to request the specified log.
        """

        cmd = self.master.mav.log_request_list_encode(
            self.master.target_system,
            self.master.target_component,
            0,                     # start id
            0xFFFF                 # end id
        )

        return cmd

    async def send_and_wait(
        self,
        *,
        match_key: str,
        request_msg: mavutil.mavlink.MAVLink_message,
        collector: Callable[[mavutil.mavlink.MAVLink_message], bool],
        timeout: float = 3.0,
    ) -> None:
        """
        Transmit *request_msg*, register a handler on *match_key* and keep feeding
        incoming packets to *collector* until it returns **True** or *timeout* expires.

        Parameters
        ----------
        match_key :
            The key used when the proxy dispatches inbound messages
            (numeric ID as string, e.g. `"147"`).
        request_msg :
            Encoded MAVLink message to send – COMMAND_LONG, LOG_REQUEST_LIST, …
        collector :
            Callback that receives each matching packet.  Must return **True**
            once the desired condition is satisfied; returning **False** keeps
            waiting.
        timeout :
            Maximum seconds to block.
        """

        # always transmit on “mav” so the proxy’s writer thread sees it
        self.send("mav", request_msg)

        done = threading.Event()

        def _handler(pkt):
            try:
                if collector(pkt):        # True => finished
                    done.set()
            except Exception as exc:
                print(f"[collector] raised: {exc}")

        self.register_handler(match_key, _handler)

        if not done.wait(timeout):
            self.unregister_handler(match_key, _handler)
            raise TimeoutError(f"No reply/condition for message id {match_key} in {timeout}s")

        self.unregister_handler(match_key, _handler)


# ──────────────────────────────────────────────────────────────────────────────
class ROS1ExternalProxy(ExternalProxy):
    """
    ROS 1 driver (rospy).  Buffers and key naming convention:

    * ``send["pub/<topic>"]``        - outbound topic messages
    * ``send["svc_client/<srv>"]``   - outbound service requests
    * ``recv["sub/<topic>"]``        - inbound topic messages
    * ``recv["svc_server/<srv>"]``   - inbound service calls
    """

    def __init__(self, node_name: str = "petal_ros_proxy", maxlen: int = 200):
        super().__init__(maxlen=maxlen)
        self.node_name = node_name
        self._pub_cache = {}        # type: Dict[str, "rospy.Publisher"]
        self._srv_client_cache = {} # type: Dict[str, "rospy.ServiceProxy"]
        self._log = logging.getLogger("ROS1ExternalProxy")

    # ------------------------ life-cycle --------------------- #
    async def start(self):
        """
        Initialise the rospy node (only once per process) and start worker.
        """
        # if not rospy.core.is_initialized():
        #     rospy.init_node(self.node_name, anonymous=True, disable_signals=True)
        return await super().start()

    # ------------------- I/O primitives --------------------- #
    def _io_read_once(self) -> List[Tuple[str, Any]]:
        """
        rospy delivers messages via callbacks → nothing to poll here.
        """
        return []

    def _io_write_once(self, batches):
        """Publish topic messages or invoke service clients."""
        for key, msgs in batches.items():
            if key.startswith("pub/"):
                topic = key[4:]
                pub = self._pub_cache.get(topic)
                if not pub:
                    # from rospy.msg import AnyMsg
                    # pub = rospy.Publisher(topic, AnyMsg, queue_size=10)
                    self._pub_cache[topic] = pub
                for m in msgs:
                    pub.publish(m)

            elif key.startswith("svc_client/"):
                srv = key[12:]
                proxy = self._srv_client_cache.get(srv)
                if not proxy:
                    continue
                for req in msgs:
                    try:
                        proxy.call(req)
                    except Exception as exc:
                        self._log.error(
                            "Failed to call service %s with request %s: %s",
                            srv, req, exc
                        )

    # ------------------- helpers exposed to petals --------- #
    def _enqueue_recv(self, key: str, msg: Any) -> None:
        """
        Internal helper to push an inbound ROS message / request into
        ``_recv`` while honouring the maxlen bound.
        """
        self._recv.setdefault(key, deque(maxlen=self._maxlen)).append(msg)
        for fn in self._handlers.get(key, []):
            fn(msg)

    # The following wrappers use the helper above so that the deque logic
    # is applied consistently even for rospy callbacks.

    def subscribe(self, topic: str, msg_class, queue_size: int = 10):
        """Create a rospy subscriber and route messages into recv buffer."""
        def _cb(msg):  # noqa: ANN001 (rospy gives a concrete type)
            self._enqueue_recv(f"sub/{topic}", msg)
        # rospy.Subscriber(topic, msg_class, _cb, queue_size=queue_size)

    def advertise_service(self, srv_name: str, srv_class, handler):
        """Expose a service server whose requests flow through the recv buffer."""
        def _wrapper(req):  # noqa: ANN001
            self._enqueue_recv(f"svc_server/{srv_name}", req)
            return handler(req)
        # rospy.Service(srv_name, srv_class, _wrapper)
