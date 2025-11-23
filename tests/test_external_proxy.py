from __future__ import annotations
import asyncio, sys, time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pymavlink import mavutil
from pymavlink.dialects.v10 import common as mavlink
from pymavlink.dialects.v20 import all as mavlink_v20

# --------------------------------------------------------------------------- #
# package under test                                                          #
# --------------------------------------------------------------------------- #
from petal_app_manager.proxies.external import (
    MavLinkExternalProxy
)

# @pytest.mark.hardware
# def test_external_proxy():
#     # Use a pytest fixture to run async test
#     asyncio.run(_test_mavlink_proxy())

async def _test_mavlink_proxy():
    # Create proxy (use a local connection - adjust as needed)
    proxy = MavLinkExternalProxy(endpoint="udp:127.0.0.1:14551", baud=57600, maxlen=200)
    
    # Track received heartbeats
    heartbeats_received = []
    
    # Register handler for HEARTBEAT messages
    def heartbeat_handler(msg):
        print(f"Received HEARTBEAT: {msg}")
        heartbeats_received.append(msg)
    
    proxy.register_handler(str(mavlink_v20.MAVLINK_MSG_ID_HEARTBEAT), heartbeat_handler)
    
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
        super().__init__(endpoint="udp:dummy:14550", baud=57600, maxlen=maxlen)
        self.sent_messages = defaultdict(list)
        self.received_messages = []
        self.master = None  # Override to avoid MAVLink connection
        
    async def start(self):
        """Override start to avoid MAVLink connection tasks."""
        # Only start the base ExternalProxy, not the MAVLink-specific parts
        from petal_app_manager.proxies.external import ExternalProxy
        await ExternalProxy.start(self)
        # Mark as connected for testing purposes
        self.connected = True
        
    def _io_read_once(self, timeout: int = 0) -> list[tuple[str, str]]:
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

    async def wait_for_burst_completion(self) -> None:
        """
        Wait for all pending burst tasks to complete.
        
        This method is useful in testing scenarios where you need to ensure
        that all burst messages have been queued before proceeding with
        assertions. It waits for all background burst tasks to finish.
        """
        if hasattr(self, '_burst_tasks') and self._burst_tasks:
            await asyncio.gather(*list(self._burst_tasks), return_exceptions=True)
    

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
    
    # Wait for the burst to complete (proper way to wait for async tasks)
    await proxy.wait_for_burst_completion()
    
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
    assert elapsed >= 0.2, f"Expected at least 0.2s, got {elapsed:.3f}s"
    
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


@pytest.mark.asyncio
async def test_burst_timing_precision():
    """Test that burst intervals are properly timed."""
    
    class TimingMockProxy(MockExternalProxy):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.message_timestamps = []
            
        async def _send_burst(self, key: str, msg: Any, count: int, interval: float) -> None:
            """Override to track timing."""
            send_queue = self._send.setdefault(key, deque(maxlen=self._maxlen))
            
            # Send messages with proper intervals and track timing
            for i in range(count):
                self.message_timestamps.append(time.time())
                send_queue.append(msg)
                self._log.debug(f"Burst message {i+1}/{count} queued for key '{key}'")
                if i < count - 1:  # Don't sleep after the last message
                    await asyncio.sleep(interval)
    
    proxy = TimingMockProxy()
    
    # Start the proxy
    await proxy.start()
    
    start_time = time.time()
    
    # Send a burst of 3 messages with 0.05 second intervals (faster for testing)
    proxy.send("test_key", "timed_burst", burst_count=3, burst_interval=0.05)
    
    # Wait for the burst to complete properly
    await proxy.wait_for_burst_completion()
    
    # Verify we got the expected number of messages
    assert len(proxy.message_timestamps) == 3, f"Expected 3 messages, got {len(proxy.message_timestamps)}"
    
    # Check that the intervals are approximately correct
    if len(proxy.message_timestamps) >= 2:
        interval1 = proxy.message_timestamps[1] - proxy.message_timestamps[0]
        interval2 = proxy.message_timestamps[2] - proxy.message_timestamps[1]
        
        # Allow some tolerance for timing (±20ms)
        assert abs(interval1 - 0.05) < 0.02, f"First interval: {interval1:.3f}s, expected ~0.05s"
        assert abs(interval2 - 0.05) < 0.02, f"Second interval: {interval2:.3f}s, expected ~0.05s"
    
    await proxy.stop()


@pytest.mark.asyncio
async def test_burst_interval_real_world_scenario():
    """Test burst sending in a real-world scenario with MAVLink heartbeats."""
    proxy = MockExternalProxy()
    
    # Track all sent messages with timestamps
    sent_messages_with_time = []
    
    # Override _io_write_once to track when messages are actually sent
    original_io_write_once = proxy._io_write_once
    def timed_io_write_once(batches):
        timestamp = time.time()
        for key, msgs in batches.items():
            for msg in msgs:
                sent_messages_with_time.append((timestamp, key, msg))
        return original_io_write_once(batches)
    
    proxy._io_write_once = timed_io_write_once
    
    # Start the proxy
    await proxy.start()
    
    # Clear any existing messages that might be in the queue
    proxy.sent_messages.clear()
    sent_messages_with_time.clear()
    
    # Send a heartbeat burst every 0.2 seconds (5 Hz) on a test key
    start_time = time.time()
    proxy.send("test_heartbeat", "HEARTBEAT_MSG", burst_count=5, burst_interval=0.2)
    
    # Wait for all messages to be queued properly
    await proxy.wait_for_burst_completion()
    
    # Manually trigger a write cycle to simulate the worker thread
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Verify all 5 messages were sent on our test key
    test_messages = [msg for _, key, msg in sent_messages_with_time if key == "test_heartbeat"]
    assert len(test_messages) == 5, f"Expected 5 heartbeat messages, got {len(test_messages)}"
    assert all(msg == "HEARTBEAT_MSG" for msg in test_messages), "All messages should be HEARTBEAT_MSG"
    
    # Verify the total time was at least 0.8 seconds (4 intervals * 0.2s)
    total_time = time.time() - start_time
    assert total_time >= 0.8, f"Expected at least 0.8s total time, got {total_time:.3f}s"
    
    await proxy.stop()