"""
MavLinkProxy
============

• Manages the single MAVLink / MAVFTP connection to the flight
  controller.
• Exposes three *async* helpers that other layers call:
      - list_ulogs()
      - download_ulog()
      - get_px4_time()
• All heavy / blocking pymavlink work runs in a thread executor so the
  FastAPI event-loop never blocks.

Dependencies (add to your core requirements):
    pymavlink>=2.4.35
    tabulate
    tqdm          # optional, for nice CLI progress if installed
    pydantic
"""

from __future__ import annotations
from pathlib import Path
from typing import Callable, Awaitable, List, Dict, Tuple, Generator, Union
import asyncio, concurrent.futures, logging, time, shutil, sys

from pydantic import BaseModel, Field

from .base import BaseProxy

from pymavlink import mavutil, mavftp
from tabulate import tabulate

try:
    from tqdm import tqdm   # noqa: F401
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False


# --------------------------------------------------------------------------- #
#  Public dataclasses returned to petals / REST                               #
# --------------------------------------------------------------------------- #

class ULogInfo(BaseModel):
    """Metadata for a ULog that resides on the PX4 SD-card."""
    remote_path: str
    size_bytes : int
    utc        : int          # epoch seconds

class Px4Time(BaseModel):
    """Current clock info reported by PX4."""
    timestamp_s: int          = Field(..., description="Unix epoch seconds")
    utc_human  : str          = Field(..., description="UTC time YYYY-MM-DD HH:MM:SS")
    source_msg : str          = Field(..., description="MAVLink msg that carried the timestamp")

# Progress callback signature used by download_ulog
ProgressCB = Callable[[float], Awaitable[None]]       # 0.0 - 1.0


# --------------------------------------------------------------------------- #
#  Implementation: the proxy object                                           #
# --------------------------------------------------------------------------- #

class MavLinkProxy(BaseProxy):
    """
    Singleton owned by PetalAppManager.  Petals never touch pymavlink
    directly - they only call the async helpers below.
    """

    def __init__(
        self,
        endpoint: str = "udp:127.0.0.1:14551",
        baud: int = 115200,
        debug: int = 0,
    ):
        self.endpoint = endpoint
        self.baud     = baud
        self.debug    = debug

        self._parser  = None                # will hold _BlockingParser
        self._loop    = None
        self._exe     = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.log      = logging.getLogger("MavLinkProxy")

    # ---- lifecycle hooks wired into FastAPI -------------------------------- #

    async def start(self):
        """Create the mavutil / MAVFTP connection in a worker thread."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Opening MAVLink connection to %s ...", self.endpoint)
        self._parser = await self._loop.run_in_executor(
            self._exe, _BlockingParser, self.endpoint, self.baud, self.debug
        )
        self.log.info("MAVLink heartbeat OK - system id %s", self._parser.system_id)

    async def stop(self):
        """Close the MAVLink connection and shutdown executor."""
        if self._parser:
            await self._loop.run_in_executor(self._exe, self._parser.close)
        self._exe.shutdown(wait=False)
        self.log.info("MavLinkProxy stopped")

    # ----------------------------------------------------------------------- #
    #  Public  async helpers                                                  #
    # ----------------------------------------------------------------------- #

    async def list_ulogs(self) -> List[ULogInfo]:
        """Return metadata for every *.ulg file on the vehicle."""
        raw = await self._loop.run_in_executor(self._exe, self._parser.list_ulogs)
        return [ULogInfo(**item) for item in raw]

    async def download_ulog(
        self,
        remote_path: str,
        local_path : Path,
        on_progress: ProgressCB | None = None,
    ) -> Path:
        """
        Fetch *remote_path* from the vehicle into *local_path*.

        Returns the Path actually written on success.
        """
        await self._loop.run_in_executor(
            self._exe, self._parser.download_ulog, remote_path, local_path, on_progress
        )
        return local_path

    async def get_px4_time(self) -> Px4Time:
        raw = await self._loop.run_in_executor(self._exe, self._parser.get_px4_time)
        return Px4Time(**raw)


# --------------------------------------------------------------------------- #
#  Everything below is “private” - runs only in the worker thread            #
# --------------------------------------------------------------------------- #

class _BlockingParser:
    """
    Thin wrapper around pymavlink / MAVFTP - **runs in a dedicated thread**.
    All methods are synchronous and blocking; the proxy wraps them in
    run_in_executor so the event-loop stays responsive.
    """

    # ---------- life-cycle -------------------------------------------------- #

    def __init__(self, endpoint: str, baud: int, debug: int, log_entries: Dict[int, Dict[str, int]]):
        self._log = logging.getLogger("MavLinkParser")

        self.master = mavutil.mavlink_connection(endpoint, baud=baud)
        if not self.master.wait_heartbeat(timeout=5):
            raise TimeoutError("Failed to receive heartbeat from vehicle")
        self._log.info("Heartbeat from sys %s, comp %s",
                       self.master.target_system, self.master.target_component)

        self.ftp = mavftp.MAVFTP(
            self.master, self.master.target_system, self.master.target_component
        )
        self.ftp.ftp_settings.debug            = debug
        self.ftp.ftp_settings.retry_time       = 0.2   # 200 ms instead of 1 s
        self.ftp.ftp_settings.burst_read_size  = 239
        self.ftp.burst_size                    = 239

        self.entries = log_entries.copy()       # {id: {"size":…, "utc":…}}

    @property
    def system_id(self):          # convenience for log message in proxy.start()
        return self.master.target_system

    def close(self):
        self.master.close()

    # ---------- public helpers (blocking) ----------------------------------- #

    # 1) list_ulogs ---------------------------------------------------------- #
    def list_ulogs(self, base="fs/microsd/log") -> List[Dict]:
        """
        Enumerate *.ulg under the SD-card and return a list of dicts
        that can be fed directly into ULogInfo(**dict).
        """
        ulog_files = list(self._walk_ulogs(base))
        if not ulog_files:
            return []

        mapping = _match_ls_to_entries(ulog_files, self.entries)
        result  = []
        for name, size, utc in mapping.values():
            result.append(
                dict(remote_path=name, size_bytes=size, utc=utc)
            )
        # sort ascending by utc
        result.sort(key=lambda x: x["utc"])
        return result

    # 2) download_ulog ------------------------------------------------------- #
    def download_ulog(
        self,
        remote_path: str,
        local_path : Path,
        on_progress: ProgressCB | None = None,
    ):
        """Blocking download with retry + tmp-file recovery."""

        # ------------------------------------------------------------------ #
        def _progress_cb(frac: float | None):
            if frac is None or on_progress is None:
                return
            asyncio.run_coroutine_threadsafe(
                on_progress(frac),                                   # type: ignore[arg-type]
                loop=asyncio.get_event_loop()
            )
        # ------------------------------------------------------------------ #

        self._log.info("Downloading %s → %s", remote_path, local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        ret = self.ftp.cmd_get(
            [remote_path, str(local_path.absolute())],
            progress_callback=lambda x: _progress_cb(x)
        )
        if ret.return_code != 0:
            raise RuntimeError(f"OpenFileRO failed: {ret.return_code}")

        self.ftp.process_ftp_reply(ret.operation_name, timeout=0)

        if not local_path.exists():
            # handle temp-file move failure
            tmp = Path(self.ftp.temp_filename)
            shutil.move(tmp, local_path)
            self._log.warning("Temp file recovered to %s", local_path)

        self._log.info("Saved %s (%.1f KiB)",
                       local_path.name, local_path.stat().st_size / 1024)
        return str(local_path)

    # ---------- internal helpers ------------------------------------------- #

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
        raise RuntimeError(f"ls('{path}') failed {retries} times, giving up")


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