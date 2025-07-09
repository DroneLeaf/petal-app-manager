# MAVLink Proxy Burst Sending and Duplicate Filtering

This document describes the new burst sending and duplicate message filtering features added to the MAVLink External Proxy.

## Features Added

### 1. Burst Sending

You can now send multiple copies of a message with optional intervals between them.

#### Usage Examples

```python
# Send a single message (original behavior)
proxy.send("mav", heartbeat_msg)

# Send 5 copies immediately
proxy.send("mav", heartbeat_msg, burst_count=5)

# Send 3 copies with 0.5 second intervals
proxy.send("mav", heartbeat_msg, burst_count=3, burst_interval=0.5)

# Convenience method for MAVLink messages
proxy.send_burst(heartbeat_msg, count=5, interval=1.0)
```

#### Parameters

- `burst_count`: Number of times to send the message (default: None for single send)
- `burst_interval`: Seconds to wait between each message (default: None for immediate sending)

### 2. Duplicate Message Filtering

You can now register handlers that filter out duplicate messages within a specified time window.

#### Usage Examples

```python
# Regular handler (no filtering)
proxy.register_handler("ATTITUDE", attitude_handler)

# Handler with duplicate filtering (filters duplicates within 0.5 seconds)
proxy.register_handler("ATTITUDE", attitude_handler, duplicate_filter_interval=0.5)

# Convenience method for MAVLink message types
proxy.register_filtered_handler("ATTITUDE", attitude_handler, duplicate_filter_seconds=0.5)

# Convenience method for MAVLink message IDs
proxy.register_filtered_handler_by_id(30, attitude_handler, duplicate_filter_seconds=0.5)
```

#### Parameters

- `duplicate_filter_interval`: Time window in seconds to filter duplicate messages (default: None for no filtering)

## How It Works

### Burst Sending

1. **Immediate Burst**: When `burst_interval` is None or 0, all messages are queued immediately
2. **Timed Burst**: When `burst_interval` is specified, messages are queued with delays using asyncio tasks

### Duplicate Filtering

1. Messages are compared using their string representation
2. Each handler maintains its own duplicate detection state
3. If the same message arrives within the filter interval, the handler is not called
4. Different handlers for the same key can have different filter settings

## Implementation Details

### New Attributes

- `_handler_configs`: Stores configuration for each handler (filter intervals, etc.)
- `_last_message_times`: Tracks the last message and timestamp for each handler

### Thread Safety

- All operations are thread-safe within the existing proxy architecture
- Duplicate filtering runs in the worker thread to avoid blocking

### Memory Management

- Message timestamps are stored per handler to prevent memory leaks
- Handler configs are cleaned up when handlers are unregistered

## Example Use Cases

### 1. Robust Command Sending

```python
# Send important commands multiple times to ensure delivery
emergency_cmd = mavlink.command_long_encode(...)
proxy.send_burst(emergency_cmd, count=3, interval=0.1)
```

### 2. High-Frequency Data Filtering

```python
# Only process unique GPS positions, ignore duplicates within 1 second
def gps_handler(msg):
    process_gps_update(msg)

proxy.register_filtered_handler(
    "GLOBAL_POSITION_INT", 
    gps_handler, 
    duplicate_filter_seconds=1.0
)
```

### 3. Heartbeat Management

```python
# Send periodic heartbeats but filter received ones to avoid spam
proxy.register_filtered_handler(
    "HEARTBEAT", 
    heartbeat_received, 
    duplicate_filter_seconds=2.0
)

# Send our own heartbeats every 5 seconds
heartbeat = proxy.master.mav.heartbeat_encode(...)
proxy.send_burst(heartbeat, count=1, interval=5.0)  # This would need to be in a loop
```

## Backwards Compatibility

All existing code will continue to work without modification:

- `proxy.send(key, msg)` works exactly as before
- `proxy.register_handler(key, handler)` works exactly as before
- Only new optional parameters have been added

## Testing

See `examples/test_burst_filtering.py` for unit tests demonstrating the functionality.
See `examples/mavlink_burst_filtering_example.py` for a complete usage example.
