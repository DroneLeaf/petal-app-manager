from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# --------------------------------------------------------------------------- #
# package under test                                                          #
# --------------------------------------------------------------------------- #
from petal_app_manager.proxies.mavlink import (
    MavLinkProxy,
    _match_ls_to_entries,
    ULogInfo,
)

# --------------------------------------------------------------------------- #
#  Helper message classes for get_px4_time parametric test                    #
# --------------------------------------------------------------------------- #

class MsgWithTimeUtc:     
    time_utc = 1612345678;          
    def get_type(self): return "AUTOPILOT_VERSION"
class MsgWithTimeBootMs:  
    time_boot_ms = 60000;           
    def get_type(self): return "AUTOPILOT_VERSION"
class MsgWithTimeUsec:    
    time_usec = 60000000;           
    def get_type(self): return "AUTOPILOT_VERSION"
class MsgWithTimestamp:  
    _timestamp = 1612345678;        
    def get_type(self): 
        return "AUTOPILOT_VERSION"
class MsgWithNoTime:                                      
    def get_type(self): 
        return "AUTOPILOT_VERSION"

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
        self.mav               = MagicMock()           # holds .command_long_send
        self._log_counter      = 0                     # for recv_match() log entries

    # ---- used by _BlockingParser boot ------------------------------------ #
    def wait_heartbeat(self, timeout=5):            # always succeeds
        return True

    # ---- used by _BlockingParser._fetch_log_entries / get_px4_time ------- #
    def recv_match(self, **kwargs):
        if kwargs.get("type") == "LOG_ENTRY":
            if self._log_counter < 2:        # we need *two* entries
                self._log_counter += 1
                idx     = self._log_counter
                mock_msg = MagicMock()
                mock_msg.id        = idx
                mock_msg.size      = 1024 if idx == 1 else 2048
                mock_msg.time_utc  = 1612345678 + (idx - 1)
                mock_msg.num_logs  = 2           # total count PX4 reports
                return mock_msg
        elif kwargs.get("type") == "AUTOPILOT_VERSION":
            if self._px4_time_msg is not None:
                return self._px4_time_msg
            # if no px4_time_msg was set, we return None to signal timeout
            return None
    
    # ---- used by _BlockingParser._send_command_long --------------------- #
    def close(self):          
        return None


class MockFTPAck:
    def __init__(self, rc=0, op=""): self.return_code, self.operation_name = rc, op
class MockFTPEntry:
    def __init__(self, name, size_b, is_dir=False): self.name, self.size_b, self.is_dir = name, size_b, is_dir

class MockFTP:
    """
    Stand-in for pymavlink.mavftp.MAVFTP that feeds predictable directory
    listings and fakes downloads.
    """
    def __init__(self, master, *a, **kw):
        self.master        = master
        self.ftp_settings  = SimpleNamespace(debug=0, retry_time=0.2)
        self.burst_size    = 239
        self.list_result   = []
        self.temp_filename = "/tmp/temp_mavftp_file"

    # -- listing ----------------------------------------------------------- #
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
        else:
            self.list_result = []
        return MockFTPAck()

    # -- download ---------------------------------------------------------- #
    def cmd_get(self, args, progress_callback=None):
        if progress_callback:
            for i in range(11):
                progress_callback(i / 10)
        Path(args[1]).write_text("mock data")
        return MockFTPAck()

    def process_ftp_reply(self, op, timeout=0):
        return MockFTPAck()

# --------------------------------------------------------------------------- #
#  Helper: build & start a proxy under the patches                            #
# --------------------------------------------------------------------------- #

from petal_app_manager.proxies import mavlink as _px    # already-imported module

def _patch_pymavlink(px4_time_msg=None):
    """Return three context-manager patches that cover every access path."""
    dummy_mavutil = SimpleNamespace(
        mavlink_connection = lambda *a, **kw: MockMavlink(
            log_entry=True, px4_time_msg=px4_time_msg
        ),
        mavlink = SimpleNamespace(MAV_CMD_REQUEST_MESSAGE = 0),
    )
    dummy_mavftp  = SimpleNamespace(MAVFTP = MockFTP)

    # 1) future imports from the package
    p_pkg = patch.multiple(
        "pymavlink",
        mavutil = dummy_mavutil,
        mavftp  = dummy_mavftp,
        create  = True,
    )
    # 2) names already bound inside the proxy module
    p_mod1 = patch.object(_px, "mavutil", dummy_mavutil, create=True)
    p_mod2 = patch.object(_px, "mavftp",  dummy_mavftp,  create=True)
    return p_pkg, p_mod1, p_mod2


async def build_proxy(px4_time_msg=None):
    p_pkg, p_mod1, p_mod2 = _patch_pymavlink(px4_time_msg)
    with p_pkg, p_mod1, p_mod2:
        proxy = MavLinkProxy(endpoint="udp:dummy:14550")  # any valid host:port
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
    """Verify threshold-size matching still works."""
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
    """Ensure proxy starts, has an FTP handle, and fetched log entries."""
    proxy = await build_proxy()
    # Reach into the private parser (OK in unit-tests)
    parser = proxy._parser
    assert parser.ftp is not None
    assert len(parser.entries) == 2
    assert parser.entries[1]["size"] == 1024
    assert parser.entries[1]["utc"]  == 1612345678
    await proxy.stop()

@pytest.mark.asyncio
async def test_list_ulogs():
    proxy = await build_proxy()
    ulogs = await proxy.list_ulogs()
    assert isinstance(ulogs[0], ULogInfo)
    paths = {u.remote_path for u in ulogs}
    assert "fs/microsd/log/2023-01-01/log1.ulg" in paths
    await proxy.stop()


@pytest.mark.asyncio
async def test_ls():
    """
    Call the low-level _ls() helper directly and verify directory info.
    """
    proxy  = await build_proxy()
    parser = proxy._parser                        # private but fine in tests
    dir_list = parser._ls("fs/microsd/log")
    assert len(dir_list) == 2

    names = {d[0] for d in dir_list}
    assert names == {"2023-01-01", "2023-01-02"}

    # each element is (name, size_b, is_dir)
    assert all(item[2] is True for item in dir_list)
    await proxy.stop()

# --------------------------------------------------------------------------- #
#  Tests – proxy download                                                     #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # -------------------------------------------------------
    #  Ensure worker-thread can find an event-loop
    # -------------------------------------------------------
    main_loop = asyncio.get_event_loop()
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: main_loop)

    # -------------------------------------------------------
    proxy   = await build_proxy()
    remote  = "fs/microsd/log/2023-01-01/log1.ulg"
    local   = tmp_path / "log1.ulg"

    progress = []
    async def on_prog(frac):     # will now succeed inside worker thread
        progress.append(frac)

    await proxy.download_ulog(remote, local, on_prog)

    assert local.exists() and local.read_text() == "mock data"
    assert progress[-1] == 1.0
    await proxy.stop()


# --------------------------------------------------------------------------- #
#  Parametric tests – get_px4_time                                            #
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "msg_cls,expect_error,expect_seconds",
    [
        (MsgWithTimeUtc,      None,        1612345678),
        (MsgWithTimeBootMs,   None,              60),
        (MsgWithTimeUsec,     None,              60),
        (MsgWithTimestamp,    None,        1612345678),
        (MsgWithNoTime,       ValueError,        None),
        (None,                TimeoutError,      None),
    ]
)
async def test_get_px4_time(msg_cls, expect_error, expect_seconds):
    px4_msg = None if msg_cls is None else msg_cls()
    proxy   = await build_proxy(px4_msg)

    if expect_error:
        with pytest.raises(expect_error):
            await proxy.get_px4_time()
    else:
        clk = await proxy.get_px4_time()
        assert clk.timestamp_s == expect_seconds
    await proxy.stop()


# --------------------------------------------------------------------------- #
#  (Optional) hardware-integration test                                       #
# --------------------------------------------------------------------------- #
@pytest.mark.hardware
@pytest.mark.asyncio
async def test_download_logs_hardware_integration():
    """
    Real-hardware integration test - skipped in CI.
    Connects to actual PX4, lists logs, downloads the first one.
    """
    try:
        proxy = MavLinkProxy(endpoint="udp:127.0.0.1:14551")
        await proxy.start()
    except Exception:
        pytest.skip("Hardware connection not available")

    ulogs = await proxy.list_ulogs()
    assert ulogs, "No ULogs on vehicle"

    remote = ulogs[15].remote_path
    local  = Path("ulog_downloads") / Path(remote).name
    local.parent.mkdir(exist_ok=True)

    await proxy.download_ulog(remote, local)
    assert local.exists() and local.stat().st_size > 0
    await proxy.stop()
