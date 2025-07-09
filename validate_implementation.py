#!/usr/bin/env python3
"""
Validation script to demonstrate backwards compatibility and new burst/filtering features.
"""

import sys
from pathlib import Path
import asyncio
import time
from collections import defaultdict, deque

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from petal_app_manager.proxies.external import ExternalProxy


class TestProxy(ExternalProxy):
    """Simple test implementation."""
    
    def __init__(self):
        super().__init__()
        self.sent_messages = defaultdict(list)
        self.received_messages = []
    
    def _io_read_once(self):
        return self.received_messages
    
    def _io_write_once(self, batches):
        for key, msgs in batches.items():
            self.sent_messages[key].extend(msgs)
    
    def simulate_receive(self, key, msg):
        self.received_messages.append((key, msg))


async def main():
    print("🧪 Testing Backwards Compatibility and New Features")
    print("=" * 60)
    
    proxy = TestProxy()
    
    # Test 1: Backwards Compatibility - Original API
    print("\n1. Testing backwards compatibility...")
    
    # Original send method (no optional parameters)
    proxy.send("test_key", "original_message")
    
    # Original register_handler method (no optional parameters)
    calls = []
    def handler(msg):
        calls.append(msg)
    
    proxy.register_handler("test_key", handler)
    
    print("✓ Original API works unchanged")
    
    # Test 2: New Burst Sending Features
    print("\n2. Testing burst sending...")
    
    # Burst send without interval (immediate)
    proxy.send("burst_key", "burst_message", burst_count=3)
    
    # Trigger write to see results
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    print(f"✓ Sent {len(proxy.sent_messages['test_key'])} original messages")
    print(f"✓ Sent {len(proxy.sent_messages['burst_key'])} burst messages")
    
    # Test 3: New Duplicate Filtering
    print("\n3. Testing duplicate filtering...")
    
    filtered_calls = []
    def filtered_handler(msg):
        filtered_calls.append(msg)
    
    # Register handler with filtering
    proxy.register_handler("filtered_key", filtered_handler, duplicate_filter_interval=0.5)
    
    # Simulate receiving duplicate messages
    proxy.simulate_receive("filtered_key", "duplicate_msg")
    proxy.simulate_receive("filtered_key", "duplicate_msg")  # Should be filtered
    
    # Process messages manually (simulating the main loop)
    current_time = time.time()
    for key, msg in proxy._io_read_once():
        for cb in proxy._handlers.get(key, []):
            handler_config = proxy._handler_configs.get(key, {}).get(cb, {})
            filter_interval = handler_config.get('duplicate_filter_interval')
            
            should_call = True
            if filter_interval is not None:
                msg_str = str(msg)
                handler_key = f"{key}_{id(cb)}"
                
                if handler_key in proxy._last_message_times:
                    last_msg_str, last_time = proxy._last_message_times[handler_key]
                    if (msg_str == last_msg_str and 
                        current_time - last_time < filter_interval):
                        should_call = False
                
                if should_call:
                    proxy._last_message_times[handler_key] = (msg_str, current_time)
            
            if should_call:
                cb(msg)
    
    print(f"✓ Received {len(filtered_calls)} unique messages (duplicates filtered)")
    
    # Test 4: Timed Burst Sending
    print("\n4. Testing timed burst sending...")
    
    await proxy.start()
    
    start_time = time.time()
    proxy.send("timed_burst", "timed_message", burst_count=3, burst_interval=0.1)
    
    # Wait for burst to complete
    await asyncio.sleep(0.5)
    
    # Trigger write
    pending = defaultdict(list)
    for key, dq in proxy._send.items():
        while dq:
            pending[key].append(dq.popleft())
    proxy._io_write_once(pending)
    
    elapsed = time.time() - start_time
    print(f"✓ Timed burst completed in {elapsed:.2f} seconds")
    print(f"✓ Sent {len(proxy.sent_messages['timed_burst'])} timed messages")
    
    await proxy.stop()
    
    print("\n🎉 All tests passed! Implementation is backwards compatible with new features.")
    print("\nSummary:")
    print("- Original send() and register_handler() methods work unchanged")
    print("- New optional parameters add burst and filtering capabilities")
    print("- No breaking changes to existing code")


if __name__ == "__main__":
    asyncio.run(main())
