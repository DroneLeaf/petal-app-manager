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
from typing import (
    Any, 
    Callable, 
    Deque, 
    Dict, 
    List, 
    Mapping, 
    Tuple, 
    Generator,
    Awaitable,
    Optional
)
import logging
from pathlib import Path
import asyncio, shutil
from pydantic import BaseModel, Field
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor

from .base import BaseProxy
from pymavlink import mavutil, mavftp
from pymavlink.mavftp_op import FTP_OP
# import rospy   # ← uncomment in ROS-enabled environments

# --------------------------------------------------------------------------- #
#  Public dataclasses returned to petals / REST                               #
# --------------------------------------------------------------------------- #

class ULogInfo(BaseModel):
    """Metadata for a ULog that resides on the PX4 SD-card."""
    index      : int          # 0-based index in the list
    remote_path: str
    size_bytes : int
    utc        : int          # epoch seconds

# Progress callback signature used by download_ulog
ProgressCB = Callable[[float], Awaitable[None]]       # 0.0 - 1.0

class DownloadCancelledException(Exception):
    """Raised when a download is cancelled by the user."""
    pass


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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._exe = ThreadPoolExecutor(max_workers=1)
        
    # ------------------------ life-cycle --------------------- #
    async def start(self):
        """Open the MAVLink connection then launch the worker thread."""
        self.master = mavutil.mavlink_connection(self.endpoint, baud=self.baud)
        self.connected = False
        
        # Try to get a heartbeat but don't block indefinitely
        try:
            # Attempt to get heartbeat once with timeout
            if self.master.wait_heartbeat(timeout=5):
                self.connected = True
                self._log.info("Heartbeat from sys %s, comp %s",
                            self.master.target_system, self.master.target_component)
            else:
                self._log.warning(
                    "No heartbeat from MAVLink endpoint %s at %d baud - continuing anyway",
                    self.endpoint, self.baud
                )
        except Exception as e:
            self._log.error(f"Error establishing MAVLink connection: {str(e)} - continuing anyway")
        
        # Start the worker thread regardless of connection status
        await super().start()
        
        # Start a background task to attempt reconnection if needed
        if not self.connected:
            asyncio.create_task(self._attempt_reconnect())
        
        self._loop = asyncio.get_running_loop()
        self._parser:_BlockingParser = await self._loop.run_in_executor(
            self._exe, 
            _BlockingParser, 
            self._log,
            self.master,
            self,
            0
        )

    async def _attempt_reconnect(self):
        """Background task to periodically try to get a heartbeat if not connected"""
        while not self.connected and self._running.is_set():
            try:
                if self.master.wait_heartbeat(timeout=2):
                    self.connected = True
                    self._log.info("Heartbeat established from sys %s, comp %s",
                                self.master.target_system, self.master.target_component)
                    break
            except Exception:
                pass
            await asyncio.sleep(10)  # Try again every 10 seconds

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

    async def get_log_entries(
        self,
        *,
        msg_id: str,
        request_msg: mavutil.mavlink.MAVLink_message,
        timeout: float = 8.0,
    ) -> Dict[int, Dict[str, int]]:
        """
        Send LOG_REQUEST_LIST and gather all LOG_ENTRY packets.
        """
        entries: Dict[int, Dict[str, int]] = {}
        expected_total = {"val": None}

        def _collector(pkt) -> bool:
            if expected_total["val"] is None:
                expected_total["val"] = pkt.num_logs
            entries[pkt.id] = {"size": pkt.size, "utc": pkt.time_utc}
            return len(entries) == expected_total["val"]

        await self.send_and_wait(
            match_key=msg_id,
            request_msg=request_msg,
            collector=_collector,
            timeout=timeout,
        )
        return entries
    
    # ------------------- exposing blocking parser methods --------- #
    async def list_ulogs(self, base: str = "fs/microsd/log") -> List[ULogInfo]:
        """Return metadata for every *.ulg file on the vehicle."""
        msg_id = str(mavutil.mavlink.MAVLINK_MSG_ID_LOG_ENTRY)
        msg = self.build_req_msg_log_request(message_id=msg_id)

        entries = await self.get_log_entries(
            msg_id=msg_id,
            request_msg=msg,
            timeout=5.0
        )

        if not entries or not isinstance(entries, dict):
            self._log.warning("No log entries found or invalid format.")
            return []

        raw = await self._loop.run_in_executor(self._exe, self._parser.list_ulogs, entries, base)
        return [ULogInfo(**item) for item in raw]

    async def download_ulog(
        self,
        remote_path: str,
        local_path: Path,
        on_progress: ProgressCB | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """
        Fetch *remote_path* from the vehicle into *local_path*.

        Returns the Path actually written on success or None if cancelled.
        """
        result = await self._loop.run_in_executor(
            self._exe, 
            self._parser.download_ulog, 
            remote_path, 
            local_path, 
            on_progress,
            cancel_event
        )
        return local_path if result else None

class _BlockingParser:
    """
    Thin wrapper around pymavlink / MAVFTP - **runs in a dedicated thread**.
    All methods are synchronous and blocking; the proxy wraps them in
    run_in_executor so the event-loop stays responsive.
    """

    # ---------- life-cycle -------------------------------------------------- #

    def __init__(
            self,
            logger: logging.Logger,
            master: mavutil.mavserial,
            mavlink_proxy: MavLinkExternalProxy,
            debug: int = 0
        ):
        self._log = logger.getChild("BlockingParser")
        self.master = master
        self.ftp = mavftp.MAVFTP(
            self.master, self.master.target_system, self.master.target_component
        )
        self.ftp.ftp_settings.debug            = debug
        self.ftp.ftp_settings.retry_time       = 0.2   # 200 ms instead of 1 s
        self.ftp.ftp_settings.burst_read_size  = 239
        self.ftp.burst_size                    = 239

        self.proxy = mavlink_proxy

    @property
    def system_id(self):          # convenience for log message in proxy.start()
        return self.master.target_system

    def close(self):
        self.master.close()

    # ---------- public helpers (blocking) ----------------------------------- #

    # 1) list_ulogs ---------------------------------------------------------- #
    def list_ulogs(self, entries: Dict[int, Dict[str, int]], base="fs/microsd/log") -> List[ULogInfo]:
        """
        Enumerate *.ulg under the SD-card and return a list of dicts
        that can be fed directly into ULogInfo(**dict).
        """

        ulog_files = list(self._walk_ulogs(base))
        if not ulog_files:
            return []

        mapping = _match_ls_to_entries(ulog_files, entries)
        # sort the mapping by utc descending
        mapping = sorted(
            mapping.values(),
            key=lambda x: [2],  # sort by utc
            reverse=True
        )
        result  = []
        for i, (name, size, utc) in enumerate(mapping):
            result.append(
                dict(index=i, remote_path=name, size_bytes=size, utc=utc)
            )
        return result

    # 2) download_ulog ------------------------------------------------------- #
    def download_ulog(
        self,
        remote_path: str,
        local_path: Path,
        on_progress: ProgressCB | None = None,
        cancel_event: threading.Event | None = None,
    ):
        """Blocking download with retry + tmp-file recovery with cancellation support."""

        # ------------------------------------------------------------------ #
        def _progress_cb(frac: float | None):
            if frac is None or on_progress is None:
                return
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                # Use our custom exception to signal cancellation
                raise DownloadCancelledException("Download cancelled by user")
                
            asyncio.run_coroutine_threadsafe(
                on_progress(frac),
                loop=self.proxy._loop
            )
        # ------------------------------------------------------------------ #

        try:
            self._log.info("Downloading %s → %s", remote_path, local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            ret = self.ftp.cmd_get(
                [remote_path, str(local_path.absolute())],
                progress_callback=lambda x: _progress_cb(x)
            )
            if ret.return_code != 0:
                raise RuntimeError(f"OpenFileRO failed: {ret.return_code}")

            # Check for cancellation before processing reply
            if cancel_event and cancel_event.is_set():
                self._reset_ftp_state()
                if local_path.exists():
                    local_path.unlink()
                return None

            # Process the reply with a try-except to handle potential issues
            try:
                self.ftp.process_ftp_reply(ret.operation_name, timeout=0)
            except DownloadCancelledException:
                # Handle cancellation gracefully
                self._log.info("Download cancelled by user")
                self._reset_ftp_state()
                if local_path.exists():
                    local_path.unlink()
                return None
            except Exception as e:
                self._log.error(f"Error processing FTP reply: {str(e)}")
                self._reset_ftp_state()
                raise

            if not local_path.exists():
                # handle temp-file move failure
                tmp = Path(self.ftp.temp_filename)
                if tmp.exists():
                    shutil.move(tmp, local_path)
                    self._log.warning("Temp file recovered to %s", local_path)

            self._log.info("Saved %s (%.1f KiB)",
                        local_path.name, local_path.stat().st_size / 1024)
            return str(local_path)
            
        except DownloadCancelledException:
            # Handle cancellation gracefully at the outer level too
            self._log.info("Download cancelled by user")
            self._reset_ftp_state()
            if local_path.exists():
                local_path.unlink()
            return None
        except Exception as e:
            self._log.error(f"Download error: {str(e)}")
            # Always reset FTP state on error
            self._reset_ftp_state()
            
            # Clean up partial file
            if local_path.exists():
                local_path.unlink()
                
            # Re-raise the original exception
            raise

    # ---------- internal helpers ------------------------------------------- #
    def _reset_ftp_state(self):
        """Reset all FTP state to handle canceled transfers properly."""
        self._log.warning("Resetting FTP state")
        try:
            # First try to terminate the current session
            self.ftp._MAVFTP__terminate_session()
            self.ftp.process_ftp_reply("TerminateSession")
        except Exception as e:
            self._log.warning(f"Error terminating session: {e}")
        
        try:
            # Then reset all sessions for good measure
            op = mavftp.OP_ResetSessions
            self.ftp._MAVFTP__send(FTP_OP(self.ftp.seq, self.ftp.session, op, 0, 0, 0, 0, None))
            self.ftp.process_ftp_reply("ResetSessions")
        except Exception as e:
            self._log.warning(f"Error resetting sessions: {e}")
            
        # Reset internal dictionaries that could cause issues
        self.ftp.active_read_sessions = {}
        
        # These are the problematic data structures that cause the KeyError
        if hasattr(self.ftp, 'read_gap_times'):
            self.ftp.read_gap_times = {}
        if hasattr(self.ftp, 'read_gaps'):
            # This should be a list, not a dict
            self.ftp.read_gaps = []
            
        # Reset session counter and tracking
        if hasattr(self.ftp, 'next_read_session'):
            self.ftp.next_read_session = 1
        if hasattr(self.ftp, 'session'):
            self.ftp.session = 0
        if hasattr(self.ftp, 'seq'):
            self.ftp.seq = 0
            
        # Reset other stateful variables
        if hasattr(self.ftp, 'read_total'):
            self.ftp.read_total = 0
        if hasattr(self.ftp, 'read_offset'):
            self.ftp.read_offset = 0
        if hasattr(self.ftp, 'remote_file_size'):
            self.ftp.remote_file_size = 0
        if hasattr(self.ftp, 'burst_state'):
            self.ftp.burst_state = 0

    def _walk_ulogs(self, base="fs/microsd/log") -> Generator[Tuple[str, int], None, None]:
        dates = self._ls(base)
        for date, _, is_dir in dates:
            if not is_dir:
                continue
            for name, size, is_dir in self._ls(f"{base}/{date}"):
                if not is_dir and name.endswith(".ulg"):
                    yield f"{base}/{date}/{name}", size

    # plain MAVFTP ls
    def _ls(self, path: str, retries=5, delay=2.0):
        for n in range(1, retries + 1):
            ack = self.ftp.cmd_list([path])
            if ack.return_code == 0:
                return list(set((e.name, e.size_b, e.is_dir) for e in self.ftp.list_result))
            time.sleep(delay)
            # soft reconnect
            self.__init__(self.master.address, self.master.baud, self.ftp.ftp_settings.debug)
        raise RuntimeError(f"ls('{path}') failed {retries}×")

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

# --------------------------------------------------------------------------- #
#  helper functions                                                           #
# --------------------------------------------------------------------------- #

def _match_ls_to_entries(
    ls_list: List[Tuple[str, int]],
    entry_dict: Dict[int, Dict[str, int]],
    threshold_size: int = 4096,
) -> Dict[str, Tuple[int, int]]:
    files  = sorted([(n, s) for n, s in ls_list], key=lambda x: x[1], reverse=True)
    entries = sorted(entry_dict.items())
    if len(files) != len(entries):
        raise ValueError("ls and entry counts differ; can't match safely")
    mapping = {}
    for log_id, info in entries:
        for i, (name, sz) in enumerate(files):
            if abs(sz - info['size']) <= threshold_size:
                files.pop(i)
                mapping[log_id] = (name, sz, info['utc'])
                break
    return mapping