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
import socket
import errno
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
from pymavlink.dialects.v20 import all as mavlink_dialect

import os
# import rospy   # ← uncomment in ROS-enabled environments

import dotenv


def setup_file_only_logger(name: str, log_file: str, level: str = "INFO") -> logging.Logger:
    """Setup a logger that only writes to files, not console."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers to avoid console output
    logger.handlers.clear()
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s — %(name)s — %(levelname)s — %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger (which might log to console)
    logger.propagate = False
    
    return logger

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
    def __init__(self, maxlen: int) -> None:
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
        self._handler_configs: Dict[str, Dict[Callable[[Any], None], Dict[str, Any]]] = (
            defaultdict(dict)
        )
        self._last_message_times: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._log = logging.getLogger(self.__class__.__name__)

    def register_handler(self, key: str, fn: Callable[[Any], None], 
                        duplicate_filter_interval: Optional[float] = None) -> None:
        """
        Attach *fn* so it fires for **every** message appended to ``_recv[key]``.

        The callback executes in the proxy thread; never block for long.
        
        Parameters
        ----------
        key : str
            The key to register the handler for.
        fn : Callable[[Any], None]
            The handler function to call for each message.
        duplicate_filter_interval : Optional[float]
            If specified, duplicate messages received within this interval (in seconds)
            will be filtered out and the handler will not be called. None disables filtering.
        """
        self._handlers[key].append(fn)
        self._handler_configs[key][fn] = {
            'duplicate_filter_interval': duplicate_filter_interval
        }

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

        # Clean up handler config
        if key in self._handler_configs and fn in self._handler_configs[key]:
            del self._handler_configs[key][fn]

        if not callbacks:              # list now empty → delete key
            del self._handlers[key]
            if key in self._handler_configs:
                del self._handler_configs[key]

    def send(self, key: str, msg: Any, burst_count: Optional[int] = None, 
             burst_interval: Optional[float] = None) -> None:
        """
        Enqueue *msg* for transmission.  The newest message is kept if the
        buffer is already full.
        
        Parameters
        ----------
        key : str
            The key to send the message on.
        msg : Any
            The message to send.
        burst_count : Optional[int]
            If specified, send the message this many times in a burst.
        burst_interval : Optional[float]
            If burst_count is specified, wait this many seconds between each message.
            If None, all messages are sent immediately.
        """
        if burst_count is None or burst_count <= 1:
            # Single message send
            self._send.setdefault(key, deque(maxlen=self._maxlen)).append(msg)
        else:
            # Burst send
            if burst_interval is None or burst_interval <= 0:
                # Send all messages immediately
                send_queue = self._send.setdefault(key, deque(maxlen=self._maxlen))
                for _ in range(burst_count):
                    send_queue.append(msg)
            else:
                # Schedule burst with intervals using a background task
                if self._loop is not None:
                    try:
                        # Check if we're in the same thread as the event loop
                        current_loop = None
                        try:
                            current_loop = asyncio.get_running_loop()
                        except RuntimeError:
                            current_loop = None
                        
                        if current_loop is self._loop:
                            # We're in the event loop thread, create task directly
                            task = asyncio.create_task(
                                self._send_burst(key, msg, burst_count, burst_interval)
                            )
                            # Store the task reference to prevent garbage collection
                            if not hasattr(self, '_burst_tasks'):
                                self._burst_tasks = set()
                            self._burst_tasks.add(task)
                            task.add_done_callback(self._burst_tasks.discard)
                        else:
                            # We're in a different thread, schedule on proxy's loop
                            def schedule_burst():
                                try:
                                    task = asyncio.create_task(
                                        self._send_burst(key, msg, burst_count, burst_interval)
                                    )
                                    if not hasattr(self, '_burst_tasks'):
                                        self._burst_tasks = set()
                                    self._burst_tasks.add(task)
                                    task.add_done_callback(self._burst_tasks.discard)
                                except Exception as e:
                                    self._log.error(f"Failed to schedule burst task: {e}")
                            
                            self._loop.call_soon_threadsafe(schedule_burst)
                    except Exception as e:
                        # If task creation fails, fall back to immediate send
                        self._log.warning(f"Failed to create burst task: {e}, sending immediately")
                        send_queue = self._send.setdefault(key, deque(maxlen=self._maxlen))
                        for _ in range(burst_count):
                            send_queue.append(msg)
                else:
                    # If no loop is available, fall back to immediate send
                    self._log.warning("No event loop available for burst with interval, sending immediately")
                    send_queue = self._send.setdefault(key, deque(maxlen=self._maxlen))
                    for _ in range(burst_count):
                        send_queue.append(msg)

    async def _send_burst(self, key: str, msg: Any, count: int, interval: float) -> None:
        """Send a burst of messages with specified interval."""
        send_queue = self._send.setdefault(key, deque(maxlen=self._maxlen))
        
        # Send messages with proper intervals
        for i in range(count):
            send_queue.append(msg)
            self._log.debug(f"Burst message {i+1}/{count} queued for key '{key}'")
            if i < count - 1:  # Don't sleep after the last message
                await asyncio.sleep(interval)

    # ───────────────────────────────────────────── FastAPI life-cycle hooks ──
    async def start(self) -> None:
        """Create the worker thread and begin polling/writing."""
        self._loop = asyncio.get_running_loop()
        self._burst_tasks = set()  # Initialize burst tasks tracking
        self._running.set()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        """Ask the worker to exit and join it (best-effort, 5 s timeout)."""
        self._running.clear()
        
        # Cancel any pending burst tasks
        if hasattr(self, '_burst_tasks'):
            for task in self._burst_tasks.copy():
                if not task.done():
                    task.cancel()
            # Wait for tasks to complete cancellation
            if self._burst_tasks:
                await asyncio.gather(*self._burst_tasks, return_exceptions=True)
                self._burst_tasks.clear()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    # ─────────────────────────────────────────────── subclass responsibilities ─
    @abstractmethod
    def _io_read_once(self, timeout: int=0) -> List[Tuple[str, Any]]:
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
        
        # Initialize sleep time for the worker loop
        sleep_time = 0.010  # Default 10ms
        try:
            if self.mavlink_worker_sleep_ms is not None:
                sleep_time_ms = int(self.mavlink_worker_sleep_ms)
                if sleep_time_ms < 0:
                    self._log.error("self.mavlink_worker_sleep_ms must be non-negative")
                    sleep_time_ms = 10
                sleep_time = sleep_time_ms / 1000.0  # convert ms to seconds
        except (ValueError, TypeError) as exc:
            self._log.error(f"Invalid self.mavlink_worker_sleep_ms: {exc}, using default 10ms")
            sleep_time = 0.010

        while self._running.is_set():
            # 1 - DRIVE OUTBOUND
            pending: Dict[str, List[Any]] = defaultdict(list)
            for key, dq in list(self._send.items()):
                while dq:
                    pending[key].append(dq.popleft())
            if pending:
                self._io_write_once(pending)

            # 2 - POLL INBOUND
            for key, msg in self._io_read_once(timeout=sleep_time):
                dq = self._recv.setdefault(key, deque(maxlen=self._maxlen))
                dq.append(msg)
                # broadcast with duplicate filtering
                current_time = time.time()
                for cb in self._handlers.get(key, []):
                    try:
                        # Check if duplicate filtering is enabled for this handler
                        handler_config = self._handler_configs.get(key, {}).get(cb, {})
                        filter_interval = handler_config.get('duplicate_filter_interval')
                        
                        should_call_handler = True
                        if filter_interval is not None:
                            # Convert message to string for comparison
                            msg_str = str(msg)
                            handler_key = f"{key}_{id(cb)}"
                            
                            # Check if we've seen this exact message recently for this handler
                            if handler_key in self._last_message_times:
                                last_msg_str, last_time = self._last_message_times[handler_key]
                                if (msg_str == last_msg_str and 
                                    current_time - last_time < filter_interval):
                                    should_call_handler = False
                                    self._log.debug(
                                        "[ExternalProxy] Filtered duplicate message for handler %s on key '%s'",
                                        cb, key
                                    )
                            
                            # Update last message time for this handler
                            if should_call_handler:
                                self._last_message_times[handler_key] = (msg_str, current_time)
                        
                        if should_call_handler:
                            cb(msg)
                            self._log.debug(
                                "[ExternalProxy] handler %s called for key '%s': %s",
                                cb, key, msg
                            )
                    except Exception as exc:          # never kill the loop
                        self._log.error(
                            "[ExternalProxy] handler %s raised: %s",
                            cb, exc
                        )

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
        endpoint: str,
        baud: int,
        maxlen: int,
        mavlink_worker_sleep_ms: float = 0,
        mavlink_heartbeat_send_frequency: float = 5.0,
        root_sd_path: str = 'fs/microsd/log'
    ):
        super().__init__(maxlen=maxlen)
        self.endpoint = endpoint
        self.baud = baud
        self.mavlink_worker_sleep_ms = mavlink_worker_sleep_ms
        self.mavlink_heartbeat_send_frequency = mavlink_heartbeat_send_frequency
        self.root_sd_path = root_sd_path
        self.master: mavutil.mavfile | None = None
        
        # Set up file-only logging
        self._log = setup_file_only_logger("MavLinkExternalProxy", "app-mavlinkexternalproxy.log", "INFO")
        
        self._loop: asyncio.AbstractEventLoop | None = None
        self._exe = ThreadPoolExecutor(max_workers=1)
        self.connected = False
        self._last_heartbeat_time = 0.0
        self._connection_check_interval = 5.0  # Check connection every 5 seconds
        self._heartbeat_timeout = 60.0  # Consider disconnected if no heartbeat for 60s
        self._reconnect_interval = 2.0  # Wait 2s between reconnection attempts
        self._heartbeat_task = None
        self._connection_monitor_task = None
        self._reconnect_pending = False
        self._mav_lock = threading.Lock()
        
        # Rate limiting for logging
        self._last_log_time = {}
        self._log_interval = {
            'HEARTBEAT': 10.0,        # Log heartbeats every 10 seconds max
            'MISSION_CURRENT': 5.0,   # Log mission current every 5 seconds max
            'ATTITUDE': 30.0,         # Log attitude every 30 seconds max
            'POSITION': 30.0,         # Log position every 30 seconds max
            'DEFAULT': 2.0            # Default interval for other messages
        }
        
        # Messages to suppress completely (only show at DEBUG level)
        self._suppress_messages = {
            'SERVO_OUTPUT_RAW',
            'ACTUATOR_MOTORS',
            'ATTITUDE_QUATERNION',
            'LOCAL_POSITION_NED',
            'GLOBAL_POSITION_INT'
        }
        
    def _should_log_message(self, msg_type: str) -> bool:
        """Determine if a message should be logged based on rate limiting"""
        import time
        current_time = time.time()
        
        # Suppress high-frequency messages completely at INFO level
        if msg_type in self._suppress_messages:
            return False
        
        # Get the appropriate interval for this message type
        interval = self._log_interval.get(msg_type, self._log_interval['DEFAULT'])
        
        # Check if enough time has passed since last log
        last_log = self._last_log_time.get(msg_type, 0.0)
        if current_time - last_log >= interval:
            self._last_log_time[msg_type] = current_time
            return True
            
        return False
        

    @property
    def target_system(self) -> int:
        """Return the target system ID of the MAVLink connection."""
        if self.master:
            return self.master.target_system
        return 0
    
    @property
    def target_component(self) -> int:
        """Return the target component ID of the MAVLink connection."""
        if self.master:
            return self.master.target_component
        return 0

    # ------------------------ life-cycle --------------------- #
    async def start(self):
        """Open the MAVLink connection then launch the worker thread."""
        self._loop = asyncio.get_running_loop()
        
        # Start the worker thread first
        await super().start()
        
        # Attempt initial connection
        self._schedule_reconnect()
        
        # Start connection monitoring and heartbeat tasks
        self._connection_monitor_task = asyncio.create_task(self._monitor_connection())
        
        # send heartbeat at configured frequency
        if self.mavlink_heartbeat_send_frequency is not None:
            try:
                frequency = float(self.mavlink_heartbeat_send_frequency)
                if frequency <= 0:
                    raise ValueError("Heartbeat frequency must be positive")
            except ValueError as exc:
                self._log.error(f"Invalid self.mavlink_heartbeat_send_frequency: {exc}")
                frequency = 5.0
            self._heartbeat_task = asyncio.create_task(self._send_heartbeat_periodically(frequency=frequency))

    async def _establish_connection(self):
        """Establish MAVLink connection and wait for heartbeat."""
        try:
            if self.master:
                try:
                    self.master.close()
                except:
                    pass  # Ignore errors when closing old connection
            
            self.master = mavutil.mavlink_connection(
                self.endpoint, 
                baud=self.baud, 
                dialect="all",
                source_system=2, 
                source_component=140  # MAV_COMP_ID_USER1–USER4 140–143
            )
            
            # Try to get a heartbeat with timeout
            try:
                if self.master.wait_heartbeat(timeout=5):
                    self.connected = True
                    self._last_heartbeat_time = time.time()
                    self._log.info("MAVLink connection established - Heartbeat from sys %s, comp %s",
                                self.master.target_system, self.master.target_component)
                    
                    # Register heartbeat handler to track connection health
                    self.register_handler(str(mavlink_dialect.MAVLINK_MSG_ID_HEARTBEAT), self._on_heartbeat_received)
                    
                else:
                    self.connected = False
                    self._log.warning("No heartbeat received from MAVLink endpoint %s", self.endpoint)
            except (OSError, socket.error) as e:
                self.connected = False
                self._log.warning(f"Socket error during heartbeat wait: {e}")
            except Exception as e:
                self.connected = False
                self._log.warning(f"Error waiting for heartbeat: {e}")
                
        except Exception as e:
            self.connected = False
            self._log.error(f"Error establishing MAVLink connection: {str(e)}")
            if self.master:
                try:
                    self.master.close()
                except:
                    pass
                self.master = None

    def _on_heartbeat_received(self, msg):
        """Handler for incoming heartbeat messages to track connection health."""
        self._last_heartbeat_time = time.time()
        if not self.connected:
            self.connected = True
            self._log.info("MAVLink connection re-established")

    async def _monitor_connection(self):
        """Monitor connection health and trigger reconnection if needed."""
        while self._running.is_set():
            try:
                # Skip monitoring if _mav_lock is held (FTP operation in progress)
                if self._mav_lock.locked():
                    await asyncio.sleep(self._connection_check_interval)
                    continue
                
                current_time = time.time()
                
                # Check if we haven't received a heartbeat recently
                if (self.connected and 
                    current_time - self._last_heartbeat_time > self._heartbeat_timeout):
                    self._log.warning("No heartbeat received for %.1fs - connection lost", 
                                    current_time - self._last_heartbeat_time)
                    self.connected = False
                
                # Attempt reconnection if not connected
                if not self.connected and self._running.is_set():
                    self._log.info("Attempting to reconnect to MAVLink...")
                    await self._establish_connection()
                    
                    if not self.connected:
                        await asyncio.sleep(self._reconnect_interval)
                
                # Check connection health periodically
                await asyncio.sleep(self._connection_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log.error(f"Error in connection monitor: {str(e)}")
                await asyncio.sleep(self._reconnect_interval)

    def _schedule_reconnect(self) -> None:
        """Called from the FTP thread when it detects a dead FD."""
        if not self._running.is_set():
            return
        # avoid stampeding: only schedule once
        if getattr(self, "_reconnect_pending", False):
            return
        self._reconnect_pending = True
        async def _task():
            try:
                await self._establish_connection()
            except Exception:
                # force a fresh BlockingParser next time only on failure
                self._parser = None
                raise
            finally:
                self._reconnect_pending = False
        asyncio.run_coroutine_threadsafe(_task(), self._loop)

    async def _send_heartbeat_periodically(self, frequency: float = 5.0):
        """Periodically send a MAVLink heartbeat message."""
        interval = 1.0 / frequency
        
        while self._running.is_set():
            try:
                if self.connected and self.master:
                    await self.send_heartbeat()
                else:
                    self._log.debug("Skipping heartbeat send - not connected")
                    
            except Exception as exc:
                self._log.error(f"Failed to send heartbeat: {exc}")
                # Don't mark as disconnected just for heartbeat send failure
                
            await asyncio.sleep(interval)

    async def send_heartbeat(self):
        """Send a MAVLink heartbeat message."""
        if not self.master:
            raise RuntimeError("MAVLink master not initialized")
            
        if not self.connected:
            raise RuntimeError("MAVLink not connected")
            
        msg = self.master.mav.heartbeat_encode(
            mavutil.mavlink.MAV_TYPE_GCS,  # GCS type
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,  # Autopilot type
            0,  # Base mode
            0,  # Custom mode
            mavutil.mavlink.MAV_STATE_ACTIVE  # System state
        )
        self.send("mav", msg)
        self._log.debug("Sent MAVLink heartbeat")

    async def stop(self):
        """Stop the worker and close the link."""
        # Cancel monitoring tasks
        if self._connection_monitor_task:
            self._connection_monitor_task.cancel()
            try:
                await self._connection_monitor_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Stop the worker thread
        await super().stop()
        
        # Close MAVLink connection
        if self.master:
            self.master.close()
            self.master = None
        
        self.connected = False

    # ------------------- I/O primitives --------------------- #
    def _io_read_once(self, timeout: float = 0.0) -> List[Tuple[str, Any]]:
        if not self.master or not self.connected:
            return []

        out: List[Tuple[str, Any]] = []
        try:
            with self._mav_lock:
                while True:
                    msg = self.master.recv_match(blocking=True, timeout=timeout)
                    if msg is None:
                        break
                    
                    msg_type = msg.get_type()
                    msg_id = msg.get_msgId()
                    
                    # Only log if rate limiting allows
                    if self._should_log_message(msg_type):
                        self._log.debug(f"📥 MAVLink RX: {msg_type} (ID: {msg_id}) - {msg}")
                    
                    out.append(("mav", msg))
                    out.append((str(msg_id), msg))
                    out.append((msg_type, msg))

        except (OSError, socket.error) as e:
            # Handle connection errors gracefully
            if e.errno in [errno.EBADF, errno.ECONNRESET, errno.ECONNREFUSED]:
                self._log.debug(f"MAVLink connection lost during read: {e}")
                # Don't mark as disconnected here, let the heartbeat monitor handle it
            else:
                self._log.error(f"Unexpected error reading MAVLink messages: {e}")
        except Exception as e:
            self._log.error(f"Error reading MAVLink messages: {e}")
            # Don't mark as disconnected here, let the heartbeat monitor handle it
        
        return out

    def _io_write_once(self, batches):
        """Send queued MAVLink messages."""
        if not self.master or not self.connected:
            return
            
        for key, msgs in batches.items():
            for msg in msgs:
                with self._mav_lock:
                    try:
                        msg_type = msg.get_type() if hasattr(msg, 'get_type') else 'UNKNOWN'
                        msg_id = msg.get_msgId() if hasattr(msg, 'get_msgId') else 'N/A'
                        
                        # Only log if rate limiting allows
                        if self._should_log_message(msg_type):
                            self._log.info(f"📤 MAVLink TX: {msg_type} (ID: {msg_id}) - {msg}")
                        
                        self.master.mav.send(msg)
                    except (OSError, socket.error) as e:
                        if e.errno in [errno.EBADF, errno.ECONNRESET, errno.ECONNREFUSED, errno.EPIPE]:
                            self._log.debug(f"MAVLink connection lost during write: {e}")
                            # Don't mark as disconnected here, let the heartbeat monitor handle it
                            break  # Stop trying to send more messages
                        else:
                            self._log.error(f"Unexpected error sending MAVLink message {key}: {e}")
                    except Exception as exc:
                        self._log.error(
                            "Failed to send MAVLink message %s: %s",
                            key, exc
                        )
                        # Don't mark as disconnected here, let the heartbeat monitor handle it

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
        
        Raises
        ------
        RuntimeError
            If MAVLink connection is not established.
        """
        if not self.master or not self.connected:
            raise RuntimeError("MAVLink connection not established")
                                
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
        
        Raises
        ------
        RuntimeError
            If MAVLink connection is not established.
        """
        if not self.master or not self.connected:
            raise RuntimeError("MAVLink connection not established")

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
        
        Raises
        ------
        RuntimeError
            If MAVLink connection is not established.
        TimeoutError
            If no matching response is received within the timeout.
        """
        if not self.connected:
            raise RuntimeError("MAVLink connection not established")

        # always transmit on "mav" so the proxy's writer thread sees it
        self.send("mav", request_msg)

        done = threading.Event()

        def _handler(pkt):
            try:
                if collector(pkt):        # True => finished
                    done.set()
            except Exception as exc:
                self._log.error(f"[collector] raised: {exc}")

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
        
class MavLinkFTPProxy(BaseProxy):
    """
    Threaded MAVLink FTP driver using :pymod:`pymavlink`.
    """

    def __init__(
        self,
        mavlink_proxy: MavLinkExternalProxy,
    ):
        self._log = logging.getLogger("MavLinkFTPProxy")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._exe = ThreadPoolExecutor(max_workers=1)
        self.mavlink_proxy: MavLinkExternalProxy = mavlink_proxy
        self._mav_lock = threading.Lock()

    # ------------------------ life-cycle --------------------- #
    async def start(self):
        """Open the MAVLink connection then launch the worker thread."""
        self._loop = asyncio.get_running_loop()
        
        # Start the worker thread first
        await super().start()

        # Initialize parser if connection was successful
        if self.mavlink_proxy.master:
            await self._init_parser()

    async def stop(self):
        """Stop the worker and close the link."""
        await asyncio.sleep(0.1)  # Ensure any pending writes are flushed
        
    # ------------------- I/O primitives --------------------- #
    async def _init_parser(self):
        """Initialize the blocking parser."""
        def create_parser():
            return _BlockingParser(
                self._log,
                self.mavlink_proxy.master,
                self.mavlink_proxy,
                0
            )
        
        self._parser = await self._loop.run_in_executor(
            self._exe, 
            create_parser
        )

    # ------------------- exposing blocking parser methods --------- #
    async def list_ulogs(self, base: str = None) -> List[ULogInfo]:
        """Return metadata for every *.ulg file on the vehicle."""
        # Check connection and attempt to establish if needed
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            raise RuntimeError("MAVLink FTP connection could not be established")

        if base is None:
            base = self.mavlink_proxy.root_sd_path

        # Initialize parser if not already done (e.g., after reconnection)
        if not hasattr(self, '_parser') or self._parser is None:
            await self._init_parser()

        # Try to get log entries from the vehicle, but handle timeout gracefully
        entries = {}
        try:
            msg_id = str(mavutil.mavlink.MAVLINK_MSG_ID_LOG_ENTRY)
            msg = self.mavlink_proxy.build_req_msg_log_request(message_id=msg_id)

            entries = await self.mavlink_proxy.get_log_entries(
                msg_id=msg_id,
                request_msg=msg,
                timeout=5.0
            )
        except (TimeoutError, RuntimeError) as e:
            self._log.warning(f"Failed to get log entries from vehicle: {e}")
            self._log.info("Attempting to list files directly via FTP without log entries...")
            entries = {}

        # Attempt to list files via FTP
        try:
            raw = await self._loop.run_in_executor(self._exe, self._parser.list_ulogs, entries, base)
            return [ULogInfo(**item) for item in raw]
        except Exception as e:
            self._log.warning(f"Failed to list files via FTP: {e}")
            return []

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
        # Check connection and attempt to establish if needed
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            self._log.warning("FTP connection not established, attempting to connect...")
            await self.mavlink_proxy._establish_connection()
            
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            raise RuntimeError("MAVLink FTP connection could not be established")

        # Initialize parser if not already done (e.g., after reconnection)
        if not hasattr(self, '_parser') or self._parser is None:
            await self._init_parser()

        result = await self._loop.run_in_executor(
            self._exe, 
            self._parser.download_ulog, 
            remote_path, 
            local_path, 
            on_progress,
            cancel_event
        )
        return local_path if result else None
    
    async def clear_error_logs(self, remote_path: str):
        """
        Clear error logs under *remote_path* from the vehicle.
        """
        # Check connection and attempt to establish if needed
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            self._log.warning("FTP connection not established, attempting to connect...")
            await self.mavlink_proxy._establish_connection()
            
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            raise RuntimeError("MAVLink FTP connection could not be established")

        # Initialize parser if not already done (e.g., after reconnection)
        if not hasattr(self, '_parser') or self._parser is None:
            await self._init_parser()

        # Try to get log entries from the vehicle, but handle timeout gracefully
        entries = {}
        try:
            msg_id = str(mavutil.mavlink.MAVLINK_MSG_ID_LOG_ENTRY)
            msg = self.mavlink_proxy.build_req_msg_log_request(message_id=msg_id)

            entries = await self.mavlink_proxy.get_log_entries(
                msg_id=msg_id,
                request_msg=msg,
                timeout=5.0
            )
        except (TimeoutError, RuntimeError) as e:
            self._log.warning(f"Failed to get log entries from vehicle: {e}")
            self._log.info("Attempting to list files directly via FTP without log entries...")
            entries = {}

        await self._loop.run_in_executor(
            self._exe, 
            self._parser.clear_error_logs, 
            remote_path
        )

    async def list_directory(self, base: str = None) -> List[str]:
        """
        List all files and directories under *base* on the vehicle.
        """
        # Check connection and attempt to establish if needed
        if not self.mavlink_proxy.master or not self.mavlink_proxy.connected:
            raise RuntimeError("MAVLink FTP connection could not be established")

        if base is None:
            base = self.mavlink_proxy.root_sd_path

        # Initialize parser if not already done (e.g., after reconnection)
        if not hasattr(self, '_parser') or self._parser is None:
            await self._init_parser()

        try:
            listing = await self._loop.run_in_executor(self._exe, self._parser.list_directory, base)
            return listing
        except Exception as e:
            self._log.warning(f"Failed to list directory via FTP: {e}")
            return []

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
        self.proxy = mavlink_proxy
        self.root_sd_path = self.proxy.root_sd_path
        
        self.ftp = mavftp.MAVFTP(
            self.master, self.master.target_system, self.master.target_component
        )
        self.ftp.ftp_settings.debug            = debug
        self.ftp.ftp_settings.retry_time       = 0.2   # 200 ms instead of 1 s
        self.ftp.ftp_settings.burst_read_size  = 239
        self.ftp.burst_size                    = 239


    @property
    def system_id(self):          # convenience for log message in proxy.start()
        return self.master.target_system

    def close(self):
        self.master.close()

    # ---------- public helpers (blocking) ----------------------------------- #

    # 1) list_ulogs ---------------------------------------------------------- #
    def list_ulogs(self, entries: Dict[int, Dict[str, int]], base:str) -> List[ULogInfo]:
        """
        Enumerate *.ulg under the SD-card and return a list of dicts
        that can be fed directly into ULogInfo(**dict).
        """

        ulog_files = list(self._walk_ulogs(base))
        if not ulog_files:
            return []

        # If we have log entries from the vehicle, try to match them with files
        if entries:
            try:
                mapping = _match_ls_to_entries(ulog_files, entries)
                # sort the mapping by utc descending
                mapping = sorted(
                    mapping.values(),
                    key=lambda x: x[2],  # sort by utc (index 2)
                    reverse=True
                )
                result = []
                for i, (name, size, utc) in enumerate(mapping):
                    result.append(
                        dict(index=i, remote_path=name, size_bytes=size, utc=utc)
                    )
                return result
            except ValueError as e:
                self._log.warning(f"Failed to match files with log entries: {e}")
                # Fall through to basic file listing
        
        # If no entries or matching failed, return basic file info without UTC timestamps
        self._log.info("Returning basic file listing without log entry metadata")
        result = []
        for i, (name, size) in enumerate(ulog_files):
            result.append(
                dict(index=i, remote_path=name, size_bytes=size, utc=0)  # UTC=0 when unknown
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._log.info("Downloading %s → %s (attempt %d/%d)", remote_path, local_path, attempt + 1, max_retries)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Check connection before download attempt
                if not self.proxy.connected:
                    self._log.warning("Connection lost, attempting to reconnect...")
                    # Try to re-establish connection
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            self.proxy._establish_connection(),
                            loop=self.proxy._loop
                        )
                        future.result(timeout=10)
                    except Exception as conn_e:
                        self._log.error(f"Reconnection failed: {conn_e}")
                        if attempt == max_retries - 1:
                            raise RuntimeError(f"Failed to reconnect after {max_retries} attempts") from conn_e
                        continue
                
                with self.proxy._mav_lock:

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
                    except (OSError, socket.error) as e:
                        self._log.error(f"FTP error during download: {str(e)}")
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

                    if not local_path.exists():
                        self._log.error("Failed to recover temp file to %s", local_path)
                        return None

                    self._log.info("Saved %s (%.1f KiB)",
                                local_path.name, local_path.stat().st_size / 1024)
                    return str(local_path)
                
            except DownloadCancelledException:
                # Handle cancellation gracefully at the outer level too
                self._log.info("Download cancelled by user")
                with self.proxy._mav_lock:
                    self._reset_ftp_state()
                if local_path.exists():
                    local_path.unlink()
                return None
            except (OSError, socket.error) as e:
                # Handle connection errors (including "Bad file descriptor")
                self._log.error(f"Download error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                with self.proxy._mav_lock:
                    self._reset_ftp_state()

                # Clean up partial file
                if local_path.exists():
                    local_path.unlink()
                
                # Mark connection as lost
                self.proxy.connected = False
                
                if attempt == max_retries - 1:
                    # Final attempt failed, re-raise
                    raise
                else:
                    # Wait before retry
                    time.sleep(1)
                    continue
            except Exception as e:
                self._log.error(f"Download error: {str(e)}")
                # Always reset FTP state on error
                with self.proxy._mav_lock:
                    self._reset_ftp_state()

                # Clean up partial file
                if local_path.exists():
                    local_path.unlink()
                    
                # Re-raise the original exception
                raise

    # 3) clear error logs ---------------------------------------------------- #
    def clear_error_logs(self, base: str = "fs/microsd") -> None:
        fail_logs = self._list_fail_logs(base)
        for log in fail_logs:
            try:
                self._log.info(f"Deleting error log {log.remote_path}")
                # Check if connection is still valid before attempting operation
                if not self.proxy.master or not self.proxy.connected:
                    self._log.warning(f"Connection lost, skipping delete for {log.remote_path}")
                    return
                self._delete(log.remote_path)
                time.sleep(0.1)  # Give some time for the delete operation to complete
            except (OSError, socket.error) as e:
                # Handle connection errors gracefully
                if e.errno in [errno.EBADF, errno.ECONNRESET, errno.ECONNREFUSED, errno.EPIPE]:
                    self._log.warning(f"Connection lost during delete operation: {e}")
                else:
                    self._log.error(f"Unexpected error deleting log {log.remote_path}: {e}")
            except Exception as e:
                self._log.error(f"Error deleting log {log.remote_path}: {e}")
        self._log.info("Cleared all error logs")

    # 4) ls a directory ------------------------------------------------------ #
    def list_directory(self, base: str = "fs/microsd") -> List[Dict[str, Any]]:
        """List the contents of a directory on the vehicle's filesystem."""
        try:
            self._log.info(f"Listing directory: {base}")
            # Check if connection is still valid before attempting operation
            if not self.proxy.master or not self.proxy.connected:
                self._log.warning(f"Connection lost, skipping ls for {base}")
                return []
            return self._ls(base)
        except Exception as e:
            self._log.error(f"Error listing directory {base}: {e}")
            return []

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
            try:
                # Check if connection is still valid before attempting operation
                if not self.master:
                    self._log.warning(f"Connection lost, skipping ls for {path}")
                    return []
                
                with self.proxy._mav_lock:
                    ack = self.ftp.cmd_list([path])
                    if ack.return_code == 0:
                        return list(set((e.name, e.size_b, e.is_dir) for e in self.ftp.list_result))
                    else:
                        # FTP command failed - check if it's a retryable error
                        if ack.return_code == 1:
                            # Error code 1 typically means "file/directory not found" or "permission denied"
                            # This is not a connection issue, so don't retry
                            self._log.warning(f"FTP ls failed: path '{path}' not found or not accessible (return code {ack.return_code})")
                            return []  # Return empty list instead of raising error
                        else:
                            # Other error codes might be retryable
                            self._log.warning(f"FTP ls command failed with return code {ack.return_code} (attempt {n}/{retries})")
                            if n >= retries:
                                raise RuntimeError(f"ls('{path}') failed after {retries} attempts: FTP return code {ack.return_code}")
                        
            except (OSError, socket.error) as e:
                # Handle connection errors gracefully
                if e.errno in [errno.EBADF, errno.ECONNRESET, errno.ECONNREFUSED, errno.EPIPE]:
                    self._log.warning(f"Connection lost during ls operation (attempt {n}/{retries}): {e}")
                    # Mark proxy as disconnected so it can reconnect
                    self.proxy.connected = False
                    # Schedule reconnect and wait for connection
                    awaitable = getattr(self.proxy, "_schedule_reconnect", None)
                    if callable(awaitable):
                        awaitable()
                    for _ in range(10):
                        if self.proxy.connected and self.master:
                            break
                        time.sleep(0.5)
                    if n >= retries:
                        raise RuntimeError(f"ls('{path}') failed after {retries} attempts due to connection loss")
                else:
                    self._log.error(f"Unexpected socket error during ls: {e}")
                    raise
            except Exception as e:
                self._log.error(f"Error during ls operation (attempt {n}/{retries}): {e}")
                if n >= retries:
                    raise RuntimeError(f"ls('{path}') failed after {retries} attempts: {e}")
            
            # If we reach here, the operation failed but we can retry
            if n < retries:
                time.sleep(delay)
                # tell the outer proxy to reconnect instead (already handled above)

        raise RuntimeError(f"ls('{path}') failed {retries}×")

    def _list_fail_logs(self, base: str = "fs/microsd") -> List[ULogInfo]:
        """
        List all fail_*.log files under the given *base* directory. without walking
        """
        try:
            entries = self._ls(base)
            fail_logs = [
                ULogInfo(index=i, remote_path=f"{base}/{name}", size_bytes=size, utc=0)
                for i, (name, size, is_dir) in enumerate(entries)
                if not is_dir and name.startswith("fail_") and name.endswith(".log")
            ]
            return fail_logs
        except RuntimeError as e:
            self._log.error(f"Failed to list fail logs in {base}: {e}")
            return []

    def _delete(self, path: str, retries=2, delay=2.0):
        """
        Delete a file or directory at *path* using MAVFTP.
        Retries on failure up to *retries* times with *delay* seconds between attempts.
        """
        for n in range(1, retries + 1):
            try:
                # Check if connection is still valid before attempting operation
                if not self.master:
                    self._log.warning(f"Connection lost, skipping delete for {path}")
                    return
                
                with self.proxy._mav_lock:
                    ack = self.ftp.cmd_rm([path])
                    if ack.return_code == 0:
                        self._log.info(f"Successfully deleted {path}")
                        return
                    else:
                        self._log.warning(f"FTP delete failed: {ack.return_code} (attempt {n}/{retries})")
                        if n >= retries:
                            raise RuntimeError(f"delete('{path}') failed after {retries} attempts: FTP return code {ack.return_code}")
                        
            except (OSError, socket.error) as e:
                # Handle connection errors gracefully
                if e.errno in [errno.EBADF, errno.ECONNRESET, errno.ECONNREFUSED, errno.EPIPE]:
                    self._log.warning(f"Connection lost during delete operation (attempt {n}/{retries}): {e}")
                    # Mark proxy as disconnected so it can reconnect
                    self.proxy.connected = False
                    # Schedule reconnect and wait for connection
                    awaitable = getattr(self.proxy, "_schedule_reconnect", None)
                    if callable(awaitable):
                        awaitable()
                    for _ in range(10):
                        if self.proxy.connected and self.master:
                            break
                        time.sleep(0.5)
                    if n >= retries:
                        raise RuntimeError(f"delete('{path}') failed after {retries} attempts due to connection loss")
                else:
                    self._log.error(f"Unexpected socket error during delete: {e}")
                    raise
            except Exception as e:
                self._log.error(f"Error during delete operation (attempt {n}/{retries}): {e}")
                if n >= retries:
                    raise RuntimeError(f"delete('{path}') failed after {retries} attempts: {e}")
            
            # If we reach here, the operation failed but we can retry
            if n < retries:
                time.sleep(delay)

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
        self._pub_cache = {}        # type: Dict[str, Any]  # rospy.Publisher
        self._srv_client_cache = {} # type: Dict[str, Any]  # rospy.ServiceProxy
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