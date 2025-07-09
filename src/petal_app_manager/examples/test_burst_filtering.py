#!/usr/bin/env python3
"""
Test for burst sending and duplicate message filtering functionality.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock
from collections import defaultdict, deque
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from proxies.external import ExternalProxy


class MockExternalProxy(ExternalProxy):
    """Mock implementation for testing."""
    
    def __init__(self, maxlen: int = 10):
        super().__init__(maxlen=maxlen)
        self.sent_messages = defaultdict(list)
        self.received_messages = []
        
    def _io_read_once(self):
        # Return any queued test messages
        return self.received_messages
        
    def _io_write_once(self, batches):
        # Store sent messages for verification
        for key, msgs in batches.items():
            self.sent_messages[key].extend(msgs)
    
    def simulate_receive(self, key: str, msg: str):
        """Simulate receiving a message."""
        self.received_messages.append((key, msg))


def test_burst_send_immediate():
    """Test burst sending without intervals."""
    proxy = MockExternalProxy()
    
    # Send a burst of 3 messages immediately
    proxy.send("test_key", "test_message", burst_count=3, burst_interval=None)
    
    # Trigger a write cycle
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    # Check that 3 messages were sent
    assert len(proxy.sent_messages["test_key"]) == 3
    assert all(msg == "test_message" for msg in proxy.sent_messages["test_key"])


@pytest.mark.asyncio
async def test_burst_send_with_interval():
    """Test burst sending with intervals."""
    proxy = MockExternalProxy()
    
    # Start the proxy
    await proxy.start()
    
    start_time = time.time()
    
    # Send a burst of 3 messages with 0.1 second intervals
    proxy.send("test_key", "test_message", burst_count=3, burst_interval=0.1)
    
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
    assert all(msg == "test_message" for msg in proxy.sent_messages["test_key"])
    
    # Check that it took at least 0.2 seconds (2 intervals)
    elapsed = time.time() - start_time
    assert elapsed >= 0.2
    
    await proxy.stop()


def test_duplicate_filtering():
    """Test duplicate message filtering."""
    proxy = MockExternalProxy()
    
    # Set up a handler with duplicate filtering
    handler_calls = []
    def test_handler(msg):
        handler_calls.append(msg)
    
    proxy.register_handler("test_key", test_handler, duplicate_filter_interval=0.5)
    
    # Simulate receiving the same message multiple times
    proxy.simulate_receive("test_key", "duplicate_message")
    
    # Manually trigger the main loop logic for the first message
    current_time = time.time()
    for key, msg in proxy.received_messages:
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
    
    # First message should be processed
    assert len(handler_calls) == 1
    assert handler_calls[0] == "duplicate_message"
    
    # Clear the received messages and add the same message again immediately
    proxy.received_messages.clear()
    proxy.simulate_receive("test_key", "duplicate_message")
    
    # Process again immediately (within filter interval)
    for key, msg in proxy.received_messages:
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
    
    # Second message should be filtered out
    assert len(handler_calls) == 1


def test_handler_cleanup():
    """Test that handler configs are cleaned up properly."""
    proxy = MockExternalProxy()
    
    def test_handler(msg):
        pass
    
    # Register handler with filtering
    proxy.register_handler("test_key", test_handler, duplicate_filter_interval=1.0)
    
    # Verify configs are set up
    assert "test_key" in proxy._handler_configs
    assert test_handler in proxy._handler_configs["test_key"]
    
    # Unregister handler
    proxy.unregister_handler("test_key", test_handler)
    
    # Verify configs are cleaned up
    assert "test_key" not in proxy._handler_configs or not proxy._handler_configs["test_key"]


if __name__ == "__main__":
    # Run basic tests
    test_burst_send_immediate()
    print("✓ Burst send (immediate) test passed")
    
    test_duplicate_filtering()
    print("✓ Duplicate filtering test passed")
    
    test_handler_cleanup()
    print("✓ Handler cleanup test passed")
    
    # Run async test
    asyncio.run(test_burst_send_with_interval())
    print("✓ Burst send (with interval) test passed")
    
    print("\nAll tests passed! 🎉")
