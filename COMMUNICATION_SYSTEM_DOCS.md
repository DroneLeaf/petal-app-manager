# Two-Way Communication System Documentation

## Overview

The RedisProxy has been enhanced with a comprehensive two-way communication system that enables reliable message exchange between the petal-app-manager and external applications like HEAR_FC. This system uses Redis as a message broker and implements best practices for distributed communication.

## Architecture

### Core Components

1. **Message Queuing**: Priority-based message queues using Redis sorted sets
2. **Pub/Sub Notifications**: Real-time message delivery notifications
3. **Status Tracking**: Application status monitoring and message acknowledgments
4. **Message Handlers**: Pluggable handlers for different message types
5. **Error Handling**: Robust error handling and recovery mechanisms

### Redis Data Structures

```
# Message Queues (Sorted Sets with Priority)
queue:{app_id}:inbox        # Incoming messages for an application
queue:{app_id}:outbox       # Outgoing messages (for monitoring)

# Application Status (Hashes)
status:{app_id}             # Application health and status information

# Message Metadata (Hashes)
message:{message_id}        # Message processing status and metadata

# Pub/Sub Channels
channel:{app_id}            # Direct notifications to specific application
channel:broadcast           # System-wide notifications
```

## Message Structure

All messages use a standardized JSON format:

```python
@dataclass
class CommunicationMessage:
    id: str                    # Unique message identifier
    sender: str               # Sending application ID
    recipient: str            # Receiving application ID
    message_type: str         # Message type for routing
    payload: Dict[str, Any]   # Message content
    priority: MessagePriority # Message priority (1-4)
    timestamp: float          # Unix timestamp
    reply_to: Optional[str]   # Original message ID for replies
    timeout: Optional[int]    # Message timeout in seconds
```

### Priority Levels

- **LOW (1)**: Background tasks, logging, statistics
- **NORMAL (2)**: Regular telemetry, status updates
- **HIGH (3)**: Commands, configuration changes
- **CRITICAL (4)**: Emergency stops, safety alerts

## API Reference

### Initialization

```python
from petal_app_manager.proxies.redis import RedisProxy, MessagePriority

# Create proxy with communication features
proxy = RedisProxy(
    host="localhost",
    port=6379,
    app_id="my-application",  # Unique application identifier
    debug=True
)

# Start the proxy
await proxy.start()
```

### Message Handlers

Register handlers for different message types:

```python
async def command_handler(message: CommunicationMessage) -> Optional[CommunicationMessage]:
    """Handle command messages."""
    command = message.payload.get("command")
    
    if command == "takeoff":
        # Execute takeoff logic
        result = execute_takeoff(message.payload.get("altitude", 10))
        
        # Return response
        return CommunicationMessage(
            id="response_id",
            sender=proxy.app_id,
            recipient=message.sender,
            message_type="command_response",
            payload={"status": "success" if result else "failed"}
        )
    
    return None

# Register the handler
await proxy.register_message_handler("command", command_handler)

# Start listening for messages
await proxy.start_listening()
```

### Sending Messages

```python
# Send a simple message
await proxy.send_message(
    recipient="HEAR_FC",
    message_type="command",
    payload={"command": "takeoff", "altitude": 20},
    priority=MessagePriority.HIGH
)

# Send message and wait for reply
response = await proxy.send_message(
    recipient="HEAR_FC",
    message_type="status_request",
    payload={"fields": ["battery", "gps"]},
    wait_for_reply=True,
    timeout=10
)

if response:
    print(f"Received reply: {response.payload}")
```

### Status Monitoring

```python
# Check if an application is online
status = await proxy.get_application_status("HEAR_FC")
if status and status.get("status") == "online":
    print("HEAR_FC is online")

# List all online applications
online_apps = await proxy.list_online_applications()
print(f"Online applications: {online_apps}")

# Check message delivery status
msg_status = await proxy.get_message_status("message_id")
print(f"Message status: {msg_status}")
```

## Common Message Types

### Commands (Control → HEAR_FC)

```python
# Takeoff command
await proxy.send_message(
    recipient="HEAR_FC",
    message_type="command",
    payload={
        "command_id": "cmd_123",
        "command": "takeoff",
        "parameters": {"altitude": 20, "speed": 2.0}
    },
    priority=MessagePriority.HIGH
)

# Emergency stop
await proxy.send_message(
    recipient="HEAR_FC",
    message_type="command",
    payload={
        "command_id": "emergency_001",
        "command": "emergency_stop",
        "parameters": {"immediate": True}
    },
    priority=MessagePriority.CRITICAL
)
```

### Telemetry (HEAR_FC → Control)

```python
# Send telemetry data
await proxy.send_message(
    recipient="petal-app-manager",
    message_type="telemetry",
    payload={
        "timestamp": time.time(),
        "battery_level": 85,
        "gps_coordinates": {"lat": 37.7749, "lon": -122.4194},
        "altitude": 50.5,
        "speed": 5.2,
        "system_status": "normal"
    },
    priority=MessagePriority.NORMAL
)
```

### Configuration

```python
# Send configuration update
await proxy.send_message(
    recipient="HEAR_FC",
    message_type="configuration",
    payload={
        "flight_mode": "autonomous",
        "max_altitude": 100,
        "geofence": {
            "enabled": True,
            "center": {"lat": 37.7749, "lon": -122.4194},
            "radius": 1000
        },
        "safety_settings": {
            "battery_low_threshold": 20,
            "auto_land_enabled": True
        }
    },
    priority=MessagePriority.HIGH
)
```

### Alerts and Notifications

```python
# Send alert
await proxy.send_message(
    recipient="petal-app-manager",
    message_type="alert",
    payload={
        "severity": "warning",
        "message": "Low battery warning",
        "details": {
            "battery_level": 15,
            "estimated_flight_time": 120
        }
    },
    priority=MessagePriority.HIGH
)
```

## Error Handling

### Connection Recovery

The system automatically handles connection failures:

```python
try:
    await proxy.send_message(recipient="HEAR_FC", message_type="ping", payload={})
except Exception as e:
    logger.error(f"Communication error: {e}")
    # System will attempt to reconnect automatically
```

### Message Timeouts

Set appropriate timeouts for time-sensitive operations:

```python
# Command with timeout
response = await proxy.send_message(
    recipient="HEAR_FC",
    message_type="emergency_command",
    payload={"action": "land_immediately"},
    wait_for_reply=True,
    timeout=5  # 5 second timeout for emergency commands
)

if not response:
    logger.error("Emergency command timed out!")
```

### Status Codes

Monitor message processing status:

```python
from petal_app_manager.proxies.redis import MessageStatus

# Check message status
status = await proxy.get_message_status("msg_123")

if status == MessageStatus.FAILED.value:
    logger.error("Message processing failed")
elif status == MessageStatus.TIMEOUT.value:
    logger.warning("Message timed out")
elif status == MessageStatus.COMPLETED.value:
    logger.info("Message processed successfully")
```

## Best Practices

### 1. Message Design

- Use clear, descriptive message types
- Include all necessary data in the payload
- Set appropriate priorities
- Include command IDs for tracking

### 2. Handler Implementation

- Keep handlers lightweight and fast
- Use async/await properly
- Return responses for commands
- Handle errors gracefully

```python
async def robust_handler(message: CommunicationMessage) -> Optional[CommunicationMessage]:
    try:
        # Process message
        result = await process_command(message.payload)
        
        return CommunicationMessage(
            id=f"response_{message.id}",
            sender=proxy.app_id,
            recipient=message.sender,
            message_type=f"{message.message_type}_response",
            payload={"status": "success", "result": result}
        )
    except Exception as e:
        logger.error(f"Handler error: {e}")
        
        return CommunicationMessage(
            id=f"error_{message.id}",
            sender=proxy.app_id,
            recipient=message.sender,
            message_type=f"{message.message_type}_response",
            payload={"status": "error", "message": str(e)}
        )
```

### 3. Resource Management

- Always call `start()` and `stop()` properly
- Use context managers when possible
- Clean up handlers on shutdown

```python
async def main():
    proxy = RedisProxy(app_id="my-app")
    
    try:
        await proxy.start()
        await proxy.register_message_handler("command", command_handler)
        await proxy.start_listening()
        
        # Your application logic here
        await asyncio.sleep(3600)  # Run for 1 hour
        
    finally:
        await proxy.stop_listening()
        await proxy.stop()
```

### 4. Monitoring and Debugging

- Use debug mode during development
- Monitor Redis memory usage
- Log important communication events
- Check application status regularly

```python
# Enable debug logging
import logging
logging.getLogger("RedisProxy").setLevel(logging.DEBUG)

# Regular health checks
async def health_monitor():
    while True:
        online_apps = await proxy.list_online_applications()
        logger.info(f"Online applications: {online_apps}")
        await asyncio.sleep(60)
```

## Performance Considerations

### Memory Management

- Redis automatically expires old message metadata
- Limit telemetry frequency to avoid overwhelming the system
- Use appropriate priority levels to manage queue sizes

### Scalability

- Each application uses separate queues
- Pub/sub scales well with multiple subscribers
- Consider Redis clustering for high-throughput scenarios

### Network Efficiency

- Batch related messages when possible
- Use compression for large payloads
- Set reasonable timeout values

## Security Considerations

1. **Authentication**: Use Redis AUTH if running in production
2. **Network Security**: Use TLS for Redis connections
3. **Message Validation**: Validate all incoming message data
4. **Access Control**: Limit Redis access to trusted applications

## Testing

The system includes comprehensive tests:

```bash
# Run unit tests
python -m pytest tests/test_redis_proxy.py -v

# Run integration test
python src/petal_app_manager/examples/integration_test_hear_fc.py
```

## Examples

- **Basic Usage**: `src/petal_app_manager/examples/hear_fc_communication_example.py`
- **Integration Test**: `src/petal_app_manager/examples/integration_test_hear_fc.py`
- **C++ Integration**: See `HEAR_FC_INTEGRATION_GUIDE.md`

## Troubleshooting

### Common Issues

1. **Redis not running**: Ensure Redis server is started
2. **Connection timeouts**: Check network connectivity
3. **Messages not received**: Verify queue names and app IDs
4. **High memory usage**: Monitor Redis memory and set appropriate TTLs

### Debug Commands

```bash
# Monitor Redis activity
redis-cli MONITOR

# Check application status
redis-cli HGETALL status:HEAR_FC

# List all queues
redis-cli KEYS "queue:*"

# Check queue contents
redis-cli ZRANGE queue:HEAR_FC:inbox 0 -1 WITHSCORES
```

This two-way communication system provides a robust, scalable foundation for integrating external applications with the petal-app-manager framework.
