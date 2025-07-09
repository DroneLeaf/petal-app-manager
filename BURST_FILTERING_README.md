# MAVLink Proxy Burst Sending and Duplicate Filtering

This document describes the new burst sending and duplicate message filtering features added to the MAVLink External Proxy. **All changes are backwards compatible** - existing code will continue to work without modification.

## Features Added

### 1. Burst Sending

You can now send multiple copies of a message with optional intervals between them using the existing `send()` method with new optional parameters.

#### Usage Examples

```python
# Send a single message (original behavior - unchanged)
proxy.send("mav", heartbeat_msg)

# Send 5 copies immediately (new feature)
proxy.send("mav", heartbeat_msg, burst_count=5)

# Send 3 copies with 0.5 second intervals (new feature)
proxy.send("mav", heartbeat_msg, burst_count=3, burst_interval=0.5)
```

#### Parameters

- `burst_count`: Number of times to send the message (default: None for single send)
- `burst_interval`: Seconds to wait between each message (default: None for immediate sending)

### 2. Duplicate Message Filtering

You can now register handlers that filter out duplicate messages within a specified time window using the existing `register_handler()` method with a new optional parameter.

#### Usage Examples

```python
# Regular handler (original behavior - unchanged)
proxy.register_handler("ATTITUDE", attitude_handler)

# Handler with duplicate filtering (new feature)
proxy.register_handler("ATTITUDE", attitude_handler, duplicate_filter_interval=0.5)
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
proxy.send("mav", emergency_cmd, burst_count=3, burst_interval=0.1)
```

### 2. High-Frequency Data Filtering

```python
# Only process unique GPS positions, ignore duplicates within 1 second
def gps_handler(msg):
    process_gps_update(msg)

proxy.register_handler(
    "GLOBAL_POSITION_INT", 
    gps_handler, 
    duplicate_filter_interval=1.0
)
```

### 3. Heartbeat Management

```python
# Send periodic heartbeats but filter received ones to avoid spam
proxy.register_handler(
    "HEARTBEAT", 
    heartbeat_received, 
    duplicate_filter_interval=2.0
)
```

## Backwards Compatibility

**100% backwards compatible** - all existing code will continue to work without modification:

- `proxy.send(key, msg)` works exactly as before
- `proxy.register_handler(key, handler)` works exactly as before
- Only new optional parameters have been added to existing methods
- No breaking changes to any existing functionality

## Testing

The burst sending and duplicate filtering functionality has been integrated into the existing test suite in `tests/test_external_proxy.py`. The tests include:

- Backwards compatibility verification
- Burst sending (immediate and timed)
- Duplicate message filtering
- Handler configuration cleanup
- Integration with MAVLink message patterns

## Migration Guide

**No migration required!** Your existing code will work unchanged. To use new features, simply add the optional parameters:

```python
# Before (still works)
proxy.send("mav", msg)
proxy.register_handler("ATTITUDE", handler)

# After (new features available)
proxy.send("mav", msg, burst_count=3, burst_interval=0.1)
proxy.register_handler("ATTITUDE", handler, duplicate_filter_interval=0.5)
```
