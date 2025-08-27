# MQTT Integration Guide for Petal App Manager

This guide explains how to integrate and use the MQTT functionality in the Petal App Manager, which provides AWS IoT MQTT broker access through a TypeScript client with callback-style message handling.

## Architecture Overview

The MQTT integration consists of three main components:

1. **MQTTProxy** - The core proxy that manages MQTT communication
2. **TypeScript MQTT Client** - External service for actual MQTT protocol handling
3. **Callback Server** - FastAPI server for receiving incoming messages with Nagle disabled for low latency

```
┌─────────────────┐    HTTP API    ┌─────────────────┐    MQTT Protocol    ┌─────────────────┐
│  Petal App      │◄──────────────►│  TypeScript     │◄───────────────────►│  AWS IoT Core   │
│  Manager        │                │  MQTT Client    │                     │  MQTT Broker    │
│  (MQTTProxy)    │                │  (Port 3004)    │                     │                 │
└─────────────────┘                └─────────────────┘                     └─────────────────┘
         ▲
         │ HTTP Callbacks
         ▼
┌─────────────────┐
│  Callback       │
│  Server         │
│  (Port 3005)    │
└─────────────────┘
```

## Configuration

### Environment Variables

Add these variables to your `.env` file:

```bash
# MQTT client configuration
TS_CLIENT_HOST=localhost
TS_CLIENT_PORT=3004
CALLBACK_HOST=localhost
CALLBACK_PORT=3005
ENABLE_CALLBACKS=true
```

### Main Application Integration

The MQTT proxy is automatically integrated into your main application:

```python
# In main.py, the MQTT proxy is added to the proxies dictionary
proxies["mqtt"] = MQTTProxy(
    local_db_proxy=proxies["db"],
    ts_client_host=Config.TS_CLIENT_HOST,
    ts_client_port=Config.TS_CLIENT_PORT,
    callback_host=Config.CALLBACK_HOST,
    callback_port=Config.CALLBACK_PORT,
    enable_callbacks=Config.ENABLE_CALLBACKS,
)
```

## API Endpoints

The MQTT functionality is exposed through REST API endpoints at `/mqtt/*`:

### Publishing Messages

```http
POST /mqtt/publish
Content-Type: application/json

{
    "topic": "org/your-org-id/device/your-device-id/telemetry",
    "payload": {
        "temperature": 23.5,
        "humidity": 65.2,
        "timestamp": "2025-08-25T10:30:00Z"
    },
    "qos": 1
}
```

### Subscribing to Topics

```http
POST /mqtt/subscribe
Content-Type: application/json

{
    "topic": "org/your-org-id/device/your-device-id/command"
}
```

### Unsubscribing from Topics

```http
POST /mqtt/unsubscribe
Content-Type: application/json

{
    "topic": "org/your-org-id/device/your-device-id/command"
}
```

### Getting Status

```http
GET /mqtt/status
```

Returns comprehensive status information including:
- Connection status to TypeScript client
- Callback server status  
- Current subscriptions
- Device information

### Listing Subscriptions

```http
GET /mqtt/subscriptions
```

Returns list of active topic subscriptions and patterns.

## Programming Interface

### Direct Proxy Usage

You can access the MQTT proxy directly in your petals:

```python
from typing import Dict, Any

async def my_petal_function(proxies):
    mqtt_proxy = proxies["mqtt"]
    
    # Publish a message
    success = await mqtt_proxy.publish_message(
        topic="test/topic",
        payload={"message": "Hello World!"},
        qos=1
    )
    
    # Subscribe with callback
    async def message_handler(topic: str, payload: Dict[str, Any]):
        print(f"Received on {topic}: {payload}")
    
    await mqtt_proxy.subscribe_to_topic("test/topic", message_handler)
    
    # Pattern subscription (local pattern matching)
    mqtt_proxy.subscribe_pattern("test/*", message_handler)
```

### Callback-Style Message Handling

The MQTT proxy follows the same callback pattern as RedisProxy:

```python
# Direct topic subscription with callback
async def command_handler(topic: str, payload: Dict[str, Any]):
    command = payload.get('command')
    message_id = payload.get('messageId')
    
    # Process command
    print(f"Executing command: {command}")
    
    # Send response
    response_topic = topic.replace('/command', '/response')
    await mqtt_proxy.publish_message(response_topic, {
        'messageId': message_id,
        'status': 'success',
        'result': 'Command executed successfully'
    })

await mqtt_proxy.subscribe_to_topic(
    f"org/{org_id}/device/{device_id}/command",
    command_handler
)

# Pattern subscription for multiple topics
async def telemetry_handler(topic: str, payload: Dict[str, Any]):
    print(f"Telemetry from {topic}: {payload}")

mqtt_proxy.subscribe_pattern("org/*/device/*/telemetry", telemetry_handler)
```

## Device Communication Patterns

### Automatic Device Topic Subscription

The proxy automatically subscribes to standard device topics when started:

- `org/{organization_id}/device/{robot_instance_id}/command`
- `org/{organization_id}/device/{robot_instance_id}/response`

These IDs are obtained from the LocalDBProxy.

### Command/Response Pattern

```python
# Commands are received automatically
# Responses are sent using the built-in command processor

# Or handle manually:
async def custom_command_handler(topic: str, payload: Dict[str, Any]):
    command_type = payload.get('command')
    message_id = payload.get('messageId')
    
    if command_type == 'get_status':
        # Handle status request
        response_data = {
            'status': 'operational',
            'uptime': get_uptime(),
            'version': '1.0.0'
        }
    elif command_type == 'restart':
        # Handle restart command
        response_data = {'status': 'restarting'}
        schedule_restart()
    
    # Send response
    response_topic = topic.replace('/command', '/response')
    await mqtt_proxy.send_command_response(
        response_topic, message_id, response_data
    )
```

### Telemetry Publishing

```python
# Regular telemetry publishing
async def publish_telemetry():
    telemetry_data = {
        'timestamp': datetime.now().isoformat(),
        'sensors': {
            'temperature': get_temperature(),
            'humidity': get_humidity(),
            'pressure': get_pressure()
        },
        'system': {
            'cpu_usage': get_cpu_usage(),
            'memory_usage': get_memory_usage(),
            'battery_level': get_battery_level()
        },
        'location': {
            'latitude': get_latitude(),
            'longitude': get_longitude(),
            'altitude': get_altitude()
        }
    }
    
    await mqtt_proxy.publish_message(
        f"org/{org_id}/device/{device_id}/telemetry",
        telemetry_data
    )

# Schedule regular telemetry
asyncio.create_task(publish_telemetry_periodically())
```

## Health Monitoring

The MQTT proxy provides comprehensive health monitoring:

```python
health_status = await mqtt_proxy.health_check()

# Check specific aspects
if health_status['connection']['ts_client']:
    print("✅ TypeScript MQTT client is accessible")

if health_status['connection']['callback_server']:
    print("✅ Callback server is running")

if health_status['connection']['connected']:
    print("✅ MQTT proxy is fully operational")
```

## Error Handling

The proxy includes robust error handling:

```python
# Publishing with error handling
try:
    success = await mqtt_proxy.publish_message(topic, payload)
    if not success:
        # Handle publish failure
        log.error(f"Failed to publish to {topic}")
except Exception as e:
    # Handle connection or other errors
    log.error(f"MQTT error: {e}")

# Subscription with error handling
try:
    await mqtt_proxy.subscribe_to_topic(topic, callback)
except Exception as e:
    log.error(f"Failed to subscribe to {topic}: {e}")
```

## Callback Server Details

The callback server runs on a separate thread with:

- **Nagle algorithm disabled** for low latency message processing
- **Separate FastAPI instance** to avoid blocking the main server
- **Automatic error handling** for malformed messages
- **Health check endpoint** at `/callback/health`

The callback server automatically processes incoming messages and routes them to registered callbacks based on topic matching and pattern subscriptions.

## Best Practices

1. **Use appropriate QoS levels**: QoS 1 for important messages, QoS 0 for frequent telemetry
2. **Pattern subscriptions**: Use sparingly and with specific patterns to avoid performance issues
3. **Error handling**: Always handle connection failures and retry logic
4. **Message size**: Keep payloads reasonable (< 128KB per AWS IoT limits)
5. **Topic naming**: Follow consistent naming conventions for your organization
6. **Health monitoring**: Regularly check proxy health status
7. **Graceful shutdown**: Ensure proper cleanup of subscriptions and connections

## Troubleshooting

### Common Issues

1. **TypeScript client not accessible**
   - Check if the TypeScript MQTT client is running on the configured port
   - Verify network connectivity to the client

2. **Callback server not receiving messages**
   - Check if the callback server is running on the correct port
   - Verify the callback URL is correctly configured in the TypeScript client

3. **Messages not being delivered**
   - Check MQTT broker connectivity
   - Verify topic permissions and AWS IoT policies
   - Check message format and size limits

4. **High latency in message processing**
   - Verify Nagle algorithm is disabled in callback server
   - Check for network congestion
   - Monitor callback processing performance

### Debug Mode

Enable debug logging for detailed information:

```python
mqtt_proxy = MQTTProxy(
    # ... other params
    debug=True
)
```

This provides detailed logging of:
- HTTP requests to TypeScript client
- Callback message processing
- Subscription management
- Error details

## Integration with Existing Petals

Existing petals can easily integrate MQTT functionality:

```python
class MyPetal:
    def __init__(self, proxies):
        self.mqtt = proxies["mqtt"]
        
    async def startup(self):
        # Subscribe to relevant topics
        await self.mqtt.subscribe_to_topic(
            "my/petal/commands", 
            self.handle_command
        )
        
        # Start telemetry publishing
        asyncio.create_task(self.publish_telemetry())
    
    async def handle_command(self, topic: str, payload: Dict[str, Any]):
        # Handle incoming commands
        pass
    
    async def publish_telemetry(self):
        # Publish regular telemetry data
        while True:
            await self.mqtt.publish_message("my/petal/telemetry", {
                "timestamp": datetime.now().isoformat(),
                "data": self.get_telemetry_data()
            })
            await asyncio.sleep(30)  # Every 30 seconds
```

This integration provides a robust, scalable MQTT solution that follows the established patterns in your Petal App Manager architecture.
