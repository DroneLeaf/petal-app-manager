# Simplified Redis Proxy Usage Guide

## Overview

The Redis proxy has been cleaned up to focus only on essential operations:
- **Key-Value operations**: `get()`, `set()`, `delete()`, `exists()`
- **Pub/Sub messaging**: `publish()`, `subscribe()`, `unsubscribe()`
- **Unix socket support**: Use `unix_socket_path` parameter

## Redis Proxy Configuration

### Unix Socket (Recommended)
```python
redis_proxy = RedisProxy(
    unix_socket_path="/tmp/redis.sock",
    db=0,
    password="your_password",  # if needed
    debug=True
)
```

### TCP Connection
```python
redis_proxy = RedisProxy(
    host="localhost",
    port=6379,
    db=0,
    password="your_password",  # if needed
    debug=True
)
```

## Usage in Petal Endpoints

### Basic Setup
```python
from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import http_endpoint

class MyPetal(Petal):
    def __init__(self):
        super().__init__()
        self.name = "my_petal"
    
    @http_endpoint(path="/my-endpoint", method="POST")
    async def my_endpoint(self, request):
        # Access Redis proxy
        redis = self.proxies["redis"]
        
        # Use Redis operations here...
```

### Key-Value Operations

#### Store Data
```python
# Simple string storage
await redis.set("user:123", "john_doe")

# With expiration (5 minutes)
await redis.set("session:abc", "active", ex=300)

# JSON data
import json
user_data = {"name": "John", "email": "john@example.com"}
await redis.set("user:data:123", json.dumps(user_data))
```

#### Retrieve Data
```python
# Get value
value = await redis.get("user:123")
if value:
    print(f"User: {value}")

# Get JSON data
user_json = await redis.get("user:data:123")
if user_json:
    user_data = json.loads(user_json)
    print(f"User: {user_data['name']}")
```

#### Check Existence and Delete
```python
# Check if key exists
if await redis.exists("user:123"):
    print("User exists")

# Delete key
deleted_count = await redis.delete("user:123")
print(f"Deleted {deleted_count} keys")
```

### Pub/Sub Operations

#### Publishing Messages
```python
@http_endpoint(path="/notify", method="POST")
async def send_notification(self, request):
    data = await request.json()
    message = data.get("message")
    
    redis = self.proxies["redis"]
    
    # Publish to a channel
    subscriber_count = await redis.publish("notifications", message)
    
    return {"sent_to": subscriber_count, "message": message}
```

#### Subscribing to Channels
```python
class MyPetal(Petal):
    def startup(self):
        super().startup()
        # Set up subscriptions when petal starts
        asyncio.create_task(self._setup_subscriptions())
    
    async def _setup_subscriptions(self):
        redis = self.proxies["redis"]
        
        # Subscribe with callback function
        await redis.subscribe("notifications", self._handle_notification)
        await redis.subscribe("commands", self._handle_command)
    
    async def _handle_notification(self, channel: str, message: str):
        self.log.info(f"Notification: {message}")
        # Process the notification...
    
    async def _handle_command(self, channel: str, message: str):
        self.log.info(f"Command received: {message}")
        # Process the command...
```

## Complete Petal Example

```python
import json
from fastapi import Request
from fastapi.responses import JSONResponse
from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import http_endpoint

class MyRedisPetal(Petal):
    def __init__(self):
        super().__init__()
        self.name = "my_redis_petal"
    
    def startup(self):
        super().startup()
        # Set up Redis subscriptions
        asyncio.create_task(self._setup_redis())
    
    async def _setup_redis(self):
        redis = self.proxies["redis"]
        await redis.subscribe("my_channel", self._handle_message)
    
    async def _handle_message(self, channel: str, message: str):
        self.log.info(f"Received: {message}")
    
    @http_endpoint(path="/store", method="POST")
    async def store_data(self, request: Request):
        """Store data in Redis"""
        data = await request.json()
        redis = self.proxies["redis"]
        
        success = await redis.set(
            f"petal:{data['key']}", 
            data['value'], 
            ex=data.get('expire')
        )
        
        return JSONResponse({"success": success})
    
    @http_endpoint(path="/get/{key}", method="GET")
    async def get_data(self, key: str):
        """Get data from Redis"""
        redis = self.proxies["redis"]
        value = await redis.get(f"petal:{key}")
        
        return JSONResponse({
            "key": key, 
            "value": value, 
            "found": value is not None
        })
    
    @http_endpoint(path="/publish", method="POST")
    async def publish_message(self, request: Request):
        """Publish message to Redis channel"""
        data = await request.json()
        redis = self.proxies["redis"]
        
        count = await redis.publish(data['channel'], data['message'])
        
        return JSONResponse({
            "channel": data['channel'],
            "subscribers": count
        })
```

## API Reference

### RedisProxy Methods

#### Key-Value Operations
- `await redis.get(key: str) -> Optional[str]`
- `await redis.set(key: str, value: str, ex: Optional[int] = None) -> bool`
- `await redis.delete(key: str) -> int`
- `await redis.exists(key: str) -> bool`

#### Pub/Sub Operations
- `await redis.publish(channel: str, message: str) -> int`
- `await redis.subscribe(channel: str, callback: Callable[[str, str], Awaitable[None]])`
- `await redis.unsubscribe(channel: str)`

### Callback Function Signature
```python
async def message_callback(channel: str, message: str) -> None:
    # Handle the received message
    pass
```

## Error Handling

The proxy handles errors gracefully:
- Returns `None` or `False` for failed operations
- Logs errors automatically
- Won't crash your application

```python
# Safe to use without try/catch
value = await redis.get("key")  # Returns None if error
success = await redis.set("key", "value")  # Returns False if error
```

## Testing

Test your Redis connection:
```python
@http_endpoint(path="/redis-test", method="GET")
async def test_redis(self):
    redis = self.proxies["redis"]
    
    # Test set/get
    await redis.set("test", "hello")
    value = await redis.get("test")
    await redis.delete("test")
    
    return JSONResponse({
        "redis_working": value == "hello"
    })
```

That's it! The simplified Redis proxy focuses on just the essentials you need for pub/sub messaging and key-value storage with Unix socket support.
