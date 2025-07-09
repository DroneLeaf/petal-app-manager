from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v10 import common as mavlink

# --------------------------------------------------------------------------- #
# package under test                                                          #
# --------------------------------------------------------------------------- #
from petal_app_manager.proxies.external import (
    MavLinkExternalProxy
)

@pytest.mark.hardware
def test_external_proxy():
    # Use a pytest fixture to run async test
    asyncio.run(_test_mavlink_proxy())

async def _test_mavlink_proxy():
    # Create proxy (use a local connection - adjust as needed)
    proxy = MavLinkExternalProxy(endpoint="udp:127.0.0.1:14551")
    
    # Track received heartbeats
    heartbeats_received = []
    
    # Register handler for HEARTBEAT messages
    def heartbeat_handler(msg):
        print(f"Received HEARTBEAT: {msg}")
        heartbeats_received.append(msg)
    
    proxy.register_handler("HEARTBEAT", heartbeat_handler)
    
    # Start the proxy
    await proxy.start()
    
    try:
        # Wait up to 5 seconds for a heartbeat
        print("Waiting for HEARTBEAT messages...")
        timeout = time.time() + 5
        while time.time() < timeout and not heartbeats_received:
            await asyncio.sleep(0.1)
        
        # Verify we got at least one heartbeat
        assert len(heartbeats_received) > 0, "No HEARTBEAT messages received"
        
        # Create and send a GPS_RAW_INT message
        print("Sending GPS_RAW_INT message...")
        mav = mavlink.MAVLink(None)
        gps_msg = mav.gps_raw_int_encode(
            time_usec=int(time.time() * 1e6),
            fix_type=3,  # 3D fix
            lat=int(45.5017 * 1e7),  # Montreal latitude
            lon=int(-73.5673 * 1e7),  # Montreal longitude
            alt=50 * 1000,  # Altitude in mm (50m)
            eph=100,  # GPS HDOP
            epv=100,  # GPS VDOP
            vel=0,  # Ground speed in cm/s
            cog=0,  # Course over ground
            satellites_visible=10,  # Number of satellites
        )
        
        # Send the message
        proxy.send("mav", gps_msg)
        
        # Wait a bit for the message to be sent
        await asyncio.sleep(0.5)
        
        print("Test complete.")
        
    finally:
        # Always stop the proxy
        await proxy.stop()

# --------------------------------------------------------------------------- #
# Test burst sending and duplicate filtering functionality                    #
# --------------------------------------------------------------------------- #

from collections import defaultdict, deque
from unittest.mock import Mock


class MockExternalProxy(MavLinkExternalProxy):
    """Mock implementation for testing burst and filtering features."""
    
    def __init__(self, maxlen: int = 10):
        super().__init__(maxlen=maxlen)
        self.sent_messages = defaultdict(list)
        self.received_messages = []
        self.master = None  # Override to avoid MAVLink connection
        
    def _io_read_once(self):
        # Return any queued test messages
        messages = self.received_messages.copy()
        self.received_messages.clear()
        return messages
        
    def _io_write_once(self, batches):
        # Store sent messages for verification
        for key, msgs in batches.items():
            self.sent_messages[key].extend(msgs)
    
    def simulate_receive(self, key: str, msg: str):
        """Simulate receiving a message."""
        self.received_messages.append((key, msg))


def test_burst_send_immediate():
    """Test burst sending without intervals (backwards compatible)."""
    proxy = MockExternalProxy()
    
    # Test backwards compatibility - single message send
    proxy.send("test_key", "single_message")
    
    # Test burst sending - 3 messages immediately
    proxy.send("test_key", "burst_message", burst_count=3, burst_interval=None)
    
    # Trigger a write cycle manually
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Check that 4 messages were sent total (1 single + 3 burst)
    assert len(proxy.sent_messages["test_key"]) == 4
    assert proxy.sent_messages["test_key"][0] == "single_message"
    assert all(msg == "burst_message" for msg in proxy.sent_messages["test_key"][1:])


@pytest.mark.asyncio
async def test_burst_send_with_interval():
    """Test burst sending with intervals."""
    proxy = MockExternalProxy()
    
    # Start the proxy
    await proxy.start()
    
    start_time = time.time()
    
    # Send a burst of 3 messages with 0.1 second intervals
    proxy.send("test_key", "timed_burst", burst_count=3, burst_interval=0.1)
    
    # Wait for the burst to complete
    await asyncio.sleep(0.5)
    
    # Trigger a write cycle
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Check that 3 messages were sent
    assert len(proxy.sent_messages["test_key"]) == 3
    assert all(msg == "timed_burst" for msg in proxy.sent_messages["test_key"])
    
    # Check that it took at least 0.2 seconds (2 intervals)
    elapsed = time.time() - start_time
    assert elapsed >= 0.2
    
    await proxy.stop()


def test_duplicate_filtering():
    """Test duplicate message filtering (backwards compatible)."""
    proxy = MockExternalProxy()
    
    # Test backwards compatibility - handler without filtering
    normal_calls = []
    def normal_handler(msg):
        normal_calls.append(msg)
    
    proxy.register_handler("normal_key", normal_handler)
    
    # Test handler with duplicate filtering
    filtered_calls = []
    def filtered_handler(msg):
        filtered_calls.append(msg)
    
    proxy.register_handler("filtered_key", filtered_handler, duplicate_filter_interval=0.5)
    
    # Simulate receiving messages
    proxy.simulate_receive("normal_key", "normal_message")
    proxy.simulate_receive("normal_key", "normal_message")  # Should not be filtered
    proxy.simulate_receive("filtered_key", "filtered_message")
    proxy.simulate_receive("filtered_key", "filtered_message")  # Should be filtered
    
    # Manually trigger the main loop logic
    current_time = time.time()
    for key, msg in proxy._io_read_once():
        dq = proxy._recv.setdefault(key, deque(maxlen=proxy._maxlen))
        dq.append(msg)
        
        for cb in proxy._handlers.get(key, []):
            handler_config = proxy._handler_configs.get(key, {}).get(cb, {})
            filter_interval = handler_config.get('duplicate_filter_interval')
            
            should_call_handler = True
            if filter_interval is not None:
                msg_str = str(msg)
                handler_key = f"{key}_{id(cb)}"
                
                if handler_key in proxy._last_message_times:
                    last_msg_str, last_time = proxy._last_message_times[handler_key]
                    if (msg_str == last_msg_str and 
                        current_time - last_time < filter_interval):
                        should_call_handler = False
                
                if should_call_handler:
                    proxy._last_message_times[handler_key] = (msg_str, current_time)
            
            if should_call_handler:
                cb(msg)
    
    # Normal handler should receive both messages
    assert len(normal_calls) == 2
    assert all(msg == "normal_message" for msg in normal_calls)
    
    # Filtered handler should receive only the first message
    assert len(filtered_calls) == 1
    assert filtered_calls[0] == "filtered_message"


def test_handler_cleanup():
    """Test that handler configs are cleaned up properly."""
    proxy = MockExternalProxy()
    
    def test_handler(msg):
        pass
    
    # Test backwards compatibility - register without filtering
    proxy.register_handler("test_key", test_handler)
    assert "test_key" in proxy._handlers
    
    # Register handler with filtering
    proxy.register_handler("filtered_key", test_handler, duplicate_filter_interval=1.0)
    
    # Verify configs are set up
    assert "filtered_key" in proxy._handler_configs
    assert test_handler in proxy._handler_configs["filtered_key"]
    
    # Unregister handlers
    proxy.unregister_handler("test_key", test_handler)
    proxy.unregister_handler("filtered_key", test_handler)
    
    # Verify configs are cleaned up
    assert "test_key" not in proxy._handlers or not proxy._handlers["test_key"]
    assert "filtered_key" not in proxy._handler_configs or not proxy._handler_configs["filtered_key"]


@pytest.mark.asyncio
async def test_mavlink_burst_integration():
    """Test burst sending with actual MAVLink-style usage."""
    proxy = MockExternalProxy()
    await proxy.start()
    
    # Simulate a MAVLink message-like object
    class MockMAVLinkMessage:
        def __init__(self, msg_type):
            self.msg_type = msg_type
        
        def __str__(self):
            return f"MAVLink_{self.msg_type}"
    
    heartbeat_msg = MockMAVLinkMessage("HEARTBEAT")
    
    # Send heartbeat burst
    proxy.send("mav", heartbeat_msg, burst_count=5)
    
    # Trigger write
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Verify burst was sent
    assert len(proxy.sent_messages["mav"]) == 5
    assert all(isinstance(msg, MockMAVLinkMessage) for msg in proxy.sent_messages["mav"])
    
    await proxy.stop()


@pytest.mark.asyncio
async def test_backwards_compatibility():
    """Ensure all existing functionality works unchanged."""
    proxy = MockExternalProxy()
    await proxy.start()
    
    received_messages = []
    def simple_handler(msg):
        received_messages.append(msg)
    
    # Test original API usage
    proxy.register_handler("test_key", simple_handler)  # No optional params
    proxy.send("test_key", "test_message")  # No optional params
    
    # Simulate message processing
    proxy.simulate_receive("test_key", "received_message")
    for key, msg in proxy._io_read_once():
        for cb in proxy._handlers.get(key, []):
            cb(msg)
    
    # Trigger send
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Verify everything works as before
    assert len(proxy.sent_messages["test_key"]) == 1
    assert proxy.sent_messages["test_key"][0] == "test_message"
    assert len(received_messages) == 1
    assert received_messages[0] == "received_message"
    
    await proxy.stop()