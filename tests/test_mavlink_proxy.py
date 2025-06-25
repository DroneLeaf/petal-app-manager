from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock
import threading

import pytest

# --------------------------------------------------------------------------- #
# package under test                                                          #
# --------------------------------------------------------------------------- #
from petal_app_manager.proxies.external import (
    MavLinkExternalProxy,
    _match_ls_to_entries,
    ULogInfo,
    _BlockingParser
)

# --------------------------------------------------------------------------- #
#  Helper message classes for tests                                           #
# --------------------------------------------------------------------------- #

class MsgWithTimeUtc:     
    time_utc = 1612345678          
    def get_type(self): return "AUTOPILOT_VERSION"
    def get_msgId(self): return 0
    
class MsgWithTimeBootMs:  
    time_boot_ms = 60000           
    def get_type(self): return "AUTOPILOT_VERSION"
    def get_msgId(self): return 0
    
class MsgWithTimeUsec:    
    time_usec = 60000000           
    def get_type(self): return "AUTOPILOT_VERSION"
    def get_msgId(self): return 0
    
class MsgWithTimestamp:  
    _timestamp = 1612345678        
    def get_type(self): return "AUTOPILOT_VERSION"
    def get_msgId(self): return 0
    
class MsgWithNoTime:                                      
    def get_type(self): return "AUTOPILOT_VERSION"
    def get_msgId(self): return 0

# --------------------------------------------------------------------------- #
#  Mocks for pymavlink                                                        #
# --------------------------------------------------------------------------- #

class MockMavlink:
    """
    Minimal stand-in for mavutil.mavlink_connection return object.
    """
    def __init__(self, log_entry=False, px4_time_msg=None):
        self.target_system     = 1
        self.target_component  = 1
        self._log_entry_sent   = not log_entry
        self._px4_time_msg     = px4_time_msg
        self.mav               = MagicMock()
        self._log_counter      = 0

    def wait_heartbeat(self, timeout=5):
        return True

    def recv_match(self, blocking=False, type=None):
        if type == "LOG_ENTRY":
            if self._log_counter < 2:
                self._log_counter += 1
                idx     = self._log_counter
                mock_msg = MagicMock()
                mock_msg.id        = idx
                mock_msg.size      = 1024 if idx == 1 else 2048
                mock_msg.time_utc  = 1612345678 + (idx - 1)
                mock_msg.num_logs  = 2
                return mock_msg
        elif type == "AUTOPILOT_VERSION":
            if self._px4_time_msg is not None:
                return self._px4_time_msg
            return None
        return None
    
    def close(self):
        return None


class MockFTPAck:
    def __init__(self, rc=0, op=""): 
        self.return_code = rc
        self.operation_name = op
        
class MockFTPEntry:
    def __init__(self, name, size_b, is_dir=False): 
        self.name = name
        self.size_b = size_b
        self.is_dir = is_dir

class MockFTP:
    """
    Stand-in for pymavlink.mavftp.MAVFTP that feeds predictable directory
    listings and fakes downloads.
    """
    def __init__(self, master, target_system=None, target_component=None, debug=0):
        self.master = master
        self.ftp_settings = SimpleNamespace(
            debug=debug, 
            retry_time=0.2,
            burst_read_size=239
        )
        self.burst_size = 239
        self.list_result = []
        self.temp_filename = "/tmp/temp_mavftp_file"

    def cmd_list(self, args):
        path = args[0]
        if path == "fs/microsd/log":
            self.list_result = [
                MockFTPEntry("2023-01-01", 0, True),
                MockFTPEntry("2023-01-02", 0, True),
            ]
        elif path == "fs/microsd/log/2023-01-01":
            self.list_result = [
                MockFTPEntry("log1.ulg", 1024, False),
                MockFTPEntry("log2.ulg", 2048, False),
            ]
        elif path == "fs/microsd/log/2023-01-02":
            self.list_result = []
        return MockFTPAck()

    def cmd_get(self, args, progress_callback=None):
        if progress_callback:
            for i in range(11):
                progress_callback(i / 10)
        Path(args[1]).write_text("mock data")
        return MockFTPAck()

    def process_ftp_reply(self, op, timeout=0):
        return MockFTPAck()

# --------------------------------------------------------------------------- #
#  Mock for _BlockingParser                                                   #
# --------------------------------------------------------------------------- #

class MockBlockingParser:
    def __init__(self, logger, master, mavlink_proxy, debug=0):
        self._log = logger.getChild("MockBlockingParser")
        self.master = master
        self.proxy = mavlink_proxy
        self.ftp = MockFTP(master, master.target_system, master.target_component)
        
    def list_ulogs(self, entries=None, base = "fs/microsd/log"):
        return [
            {"index": 0, "remote_path": f"{base}/2023-01-01/log1.ulg", "size_bytes": 1024, "utc": 1612345678},
            {"index": 1, "remote_path": f"{base}/2023-01-01/log2.ulg", "size_bytes": 2048, "utc": 1612345679}
        ]
        
    def download_ulog(self, remote_path, local_path, on_progress=None, cancel_event=None):
        # Simulate download with progress
        if on_progress:
            for i in range(11):
                asyncio.run_coroutine_threadsafe(
                    on_progress(i / 10.0),
                    self.proxy._loop
                )
                time.sleep(0.01)
        
        # Create the output file
        local_path.write_text("mock data")
        return str(local_path)
        
    def _ls(self, path):
        if path == "fs/microsd/log":
            return [
                ("2023-01-01", 0, True),
                ("2023-01-02", 0, True),
            ]
        elif path == "fs/microsd/log/2023-01-01":
            return [
                ("log1.ulg", 1024, False),
                ("log2.ulg", 2048, False),
            ]
        return []

# --------------------------------------------------------------------------- #
#  Helper: build & start a proxy under the patches                            #
# --------------------------------------------------------------------------- #

from petal_app_manager.proxies import external as _px

def _patch_pymavlink(px4_time_msg=None):
    """Return context-manager patches for testing."""
    dummy_mavutil = SimpleNamespace(
        mavlink_connection = lambda *a, **kw: MockMavlink(
            log_entry=True, px4_time_msg=px4_time_msg
        ),
        mavlink = SimpleNamespace(
            MAV_CMD_REQUEST_MESSAGE = 0,
            MAVLINK_MSG_ID_LOG_ENTRY = 118
        ),
    )
    dummy_mavftp = SimpleNamespace(MAVFTP = MockFTP)

    # Patches
    p_pkg = patch.multiple(
        "pymavlink",
        mavutil = dummy_mavutil,
        mavftp = dummy_mavftp,
        create = True,
    )
    p_mod1 = patch.object(_px, "mavutil", dummy_mavutil, create=True)
    p_mod2 = patch.object(_px, "mavftp", dummy_mavftp, create=True)
    
    # New patch for _BlockingParser
    p_mod3 = patch.object(_px, "_BlockingParser", MockBlockingParser)
    
    return p_pkg, p_mod1, p_mod2, p_mod3


async def build_proxy(px4_time_msg=None):
    p_pkg, p_mod1, p_mod2, p_mod3 = _patch_pymavlink(px4_time_msg)
    with p_pkg, p_mod1, p_mod2, p_mod3:
        proxy = MavLinkExternalProxy(endpoint="udp:dummy:14550")
        await proxy.start()
        return proxy

# --------------------------------------------------------------------------- #
#  Pytest fixtures                                                            #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def event_loop():
    """Provide a session-wide asyncio loop (pytest-asyncio)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def hardware_cleanup():
    """Fixture to ensure hardware resources are released if test is interrupted."""
    cancel_events = []
    
    def register_event(event):
        cancel_events.append(event)
        
    yield register_event
    
    # This runs even if test is aborted or fails
    for event in cancel_events:
        if not event.is_set():
            print("Cleaning up hardware resources...")
            event.set()

# --------------------------------------------------------------------------- #
#  Tests – pure helper function                                               #
# --------------------------------------------------------------------------- #

def test_match_ls_to_entries_success():
    ls_list = [
        ("file1.ulg", 1024),
        ("file2.ulg", 2048)
    ]
    entry_dict = {
        1: {'size': 1024, 'utc': 1612345678},
        2: {'size': 2048, 'utc': 1612345679}
    }
    result = _match_ls_to_entries(ls_list, entry_dict, threshold_size=1)
    assert len(result) == 2
    assert result[1][0] == "file1.ulg"
    assert result[2][0] == "file2.ulg"


def test_match_ls_to_entries_count_mismatch():
    with pytest.raises(ValueError):
        _match_ls_to_entries([("file1.ulg", 1024)], {1: {"size": 1024, "utc": 0}, 2: {"size": 2048, "utc": 1}})


def test_match_ls_to_entries_size_tolerance():
    ls_list = [("file1.ulg", 1024), ("file2.ulg", 2050)]
    entry_dict = {
        1: {"size": 1024, "utc": 111},
        2: {"size": 2048, "utc": 222},
    }
    res = _match_ls_to_entries(ls_list, entry_dict, threshold_size=100)
    assert len(res) == 2
    assert res[2][0] == "file2.ulg"

# --------------------------------------------------------------------------- #
#  Tests – proxy init / list / ls / walk                                      #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_init():
    """Ensure proxy starts and has an FTP handle."""
    proxy = await build_proxy()
    # The parser is now initialized in start()
    assert proxy._parser is not None
    assert proxy._parser.ftp is not None
    await proxy.stop()

@pytest.mark.asyncio
async def test_list_ulogs():
    # Setup with patched get_log_entries to avoid timeout
    p_pkg, p_mod1, p_mod2, p_mod3 = _patch_pymavlink()
    with p_pkg, p_mod1, p_mod2, p_mod3:
        proxy = MavLinkExternalProxy(endpoint="udp:dummy:14550")
        
        # Patch the get_log_entries method to return mock data directly
        async def mock_get_log_entries(**kwargs):
            return {
                1: {"size": 1024, "utc": 1612345678},
                2: {"size": 2048, "utc": 1612345679}
            }
        
        # Apply the patch
        with patch.object(proxy, 'get_log_entries', mock_get_log_entries):
            await proxy.start()
            ulogs = await proxy.list_ulogs()
            
            # Check results
            assert isinstance(ulogs[0], ULogInfo)
            assert len(ulogs) == 2
            paths = {u.remote_path for u in ulogs}
            assert "fs/microsd/log/2023-01-01/log1.ulg" in paths
            
            await proxy.stop()

@pytest.mark.asyncio
async def test_ls():
    """Test directory listing through mock."""
    proxy = await build_proxy()
    
    # Access through mock BlockingParser's _ls method
    dir_list = proxy._parser._ls("fs/microsd/log")
    assert len(dir_list) == 2
    
    names = {d[0] for d in dir_list}
    assert names == {"2023-01-01", "2023-01-02"}
    
    # Verify directory flags
    assert all(item[2] is True for item in dir_list)
    await proxy.stop()

# --------------------------------------------------------------------------- #
#  Tests – proxy download                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Ensure worker-thread can find an event-loop
    main_loop = asyncio.get_event_loop()
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: main_loop)

    proxy = await build_proxy()
    remote = "fs/microsd/log/2023-01-01/log1.ulg"
    local = tmp_path / "log1.ulg"

    progress = []
    async def on_prog(frac):
        progress.append(frac)

    await proxy.download_ulog(remote, local, on_prog)

    assert local.exists() and local.read_text() == "mock data"
    assert progress[-1] == 1.0
    await proxy.stop()

# --------------------------------------------------------------------------- #
#  (Optional) hardware-integration test                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.hardware
@pytest.mark.asyncio
async def test_download_logs_hardware_integration(hardware_cleanup):
    """
    Real-hardware integration test - skipped in CI.
    Connects to actual PX4, lists logs, downloads the first one.
    """
    cancel_event = threading.Event()
    hardware_cleanup(cancel_event) # Register cleanup event
    
    try:
        proxy = MavLinkExternalProxy(endpoint="udp:127.0.0.1:14551")
        await proxy.start()
    except Exception:
        pytest.skip("Hardware connection not available")

    try:
        ulogs = await proxy.list_ulogs("/fs/microsd/log")
        if not ulogs or len(ulogs) == 0:
            pytest.skip("No ULogs found on vehicle")

        # find the smallest file to download
        smallest = min(ulogs, key=lambda u: u.size_bytes)
        remote = smallest.remote_path
        print(f"Downloading {remote}...")

        local = Path("ulog_downloads") / Path(remote).name
        local.parent.mkdir(exist_ok=True)

        async def on_progress(frac):
            print(f"Download progress: {frac * 100:.1f}%")

        await proxy.download_ulog(remote, local, on_progress=on_progress, cancel_event=cancel_event)

        if not local.exists():
            pytest.fail(f"Download failed: {remote} -> {local}")
        assert local.exists() and local.stat().st_size > 0
    finally:
        # Local cleanup - happens even if test fails
        if not cancel_event.is_set():
            cancel_event.set()
        await proxy.stop()
