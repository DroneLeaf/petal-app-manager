# MQTT Petal Integration Guide

## Overview

This guide describes the refactored MQTT proxy architecture and how to structure petals to integrate with MQTT command handling. The refactor introduces a cleaner, more maintainable approach to MQTT communication with automatic organization ID monitoring and handler-based message dispatching.

---

## Table of Contents

1. [MQTT Proxy Refactor Changes](#mqtt-proxy-refactor-changes)
2. [Key Architecture Changes](#key-architecture-changes)
3. [Petal Structure for MQTT Integration](#petal-structure-for-mqtt-integration)
4. [Step-by-Step Implementation Guide](#step-by-step-implementation-guide)
5. [Complete Example](#complete-example)
6. [Migration from Old Pattern](#migration-from-old-pattern)
7. [Testing MQTT Commands](#testing-mqtt-commands)

---

## MQTT Proxy Refactor Changes

### Main Changes to MQTTProxy

#### 1. **Handler-Based Subscription Model**

**Before:**
- Petals could subscribe to arbitrary topics using `subscribe_to_topic(topic, callback)`
- Each petal managed its own topic subscriptions

**After:**
- Petals register handlers for the `command/edge` topic using `register_handler(callback)`
- All command messages flow through registered handlers
- Single subscription per petal with command-based routing

#### 2. **Simplified Public API**

**New Public Methods:**
```python
# Register a handler for command/edge topic
def register_handler(handler: Callable) -> str:
    """Returns subscription_id for later unregistration"""

# Unregister a handler
def unregister_handler(subscription_id: str) -> bool:
    """Remove handler using its subscription_id"""

# Publish to command/web topic
async def publish_message(payload: Dict[str, Any], qos: int = 1) -> bool:
    """Publish message to command/web topic"""

# Send response to response topic
async def send_command_response(message_id: str, response_data: Dict[str, Any]) -> bool:
    """Send command response with automatic topic routing"""
```

**Removed Public Methods:**
- `subscribe_to_topic()` - Now private
- `unsubscribe_from_topic()` - Now private
- `subscribe_pattern()` - Removed (use command-based routing instead)

#### 3. **Organization ID Monitoring**

- MQTT proxy now monitors organization ID availability through `OrganizationManager`
- On-demand fetching of organization ID via `_get_organization_id()`
- Automatic base topic construction when organization ID becomes available

#### 4. **Deque-Based Message Buffering**

- Multi-threaded message processing with worker threads
- Duplicate message filtering based on `messageId`
- Buffer overflow protection with configurable size

---

## Key Architecture Changes

### Message Flow

```
┌─────────────────┐
│  MQTT Broker    │
│  (AWS IoT)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  TypeScript Client              │
│  (External MQTT Client)         │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  MQTTProxy Callback Server      │
│  - Receives messages via HTTP   │
│  - Enqueues to message buffer   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Worker Threads                 │
│  - Process message buffer       │
│  - Invoke registered handlers   │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Petal Handler                  │
│  - _master_command_handler      │
│  - Routes to specific handlers  │
└─────────────────────────────────┘
```

### Topic Structure

```
org/{organization_id}/device/{device_id}/
├── command          # Command messages from edge/cloud
├── command/web      # Command messages from web client
├── response         # Response messages to cloud
└── debug            # Debug messages
```

### Handler Registration Flow

```python
# 1. Petal registers handler
subscription_id = mqtt_proxy.register_handler(self._master_command_handler)

# 2. MQTT proxy adds handler to command/edge topic
# Topic: org/{org_id}/device/{device_id}/command

# 3. When message arrives, worker thread processes it
# Calls: _master_command_handler(topic, message)

# 4. Master handler routes based on command field
# Calls: specific_handler(topic, message)
```

---

## Petal Structure for MQTT Integration

### Required Components

A petal that uses MQTT should have the following structure:

#### 1. **Class Attribute: `use_mqtt_proxy`**

```python
class MyPetal(Petal):
    name = "my-petal"
    version = "1.0.0"
    use_mqtt_proxy = True  # ← Enable MQTT-aware startup
```

This enables automatic organization ID monitoring and MQTT setup.

#### 2. **Initialization**

```python
def __init__(self):
    super().__init__()
    self._mqtt_proxy = None
    self._loop = None
    self._command_handlers = None
    self.mqtt_subscription_id = None
```

#### 3. **Startup Method**

```python
def startup(self) -> None:
    """Called when petal is started (sync)."""
    super().startup()
    # Get MQTT proxy reference
    self._mqtt_proxy = self._proxies.get("mqtt")
```

#### 4. **Async Startup (Optional)**

```python
async def async_startup(self) -> None:
    """
    Called after startup for async operations.
    
    Note: If use_mqtt_proxy=True, the main app handles:
    - Setting self._loop
    - Waiting for organization ID
    - Calling self._setup_mqtt_topics() when ready
    """
    pass  # Can be empty or add custom async logic
```

#### 5. **MQTT Setup Method** (Required)

```python
async def _setup_mqtt_topics(self):
    """
    Setup MQTT topics and handlers.
    Called by main app when organization ID is available.
    """
    # Initialize command handlers registry
    self._command_handlers = self._setup_command_handlers()
    
    # Register master handler
    self.mqtt_subscription_id = self._mqtt_proxy.register_handler(
        self._master_command_handler
    )
    
    if self.mqtt_subscription_id is None:
        logger.error(f"Failed to register MQTT handler for {self.name}")
        return
    
    logger.info(f"MQTT setup completed for {self.name}")
```

#### 6. **Command Handlers Registry**

```python
def _setup_command_handlers(self) -> Dict[str, Callable]:
    """Map command names to handler methods."""
    return {
        "my-petal/do_something": self._do_something_handler,
        "my-petal/do_another": self._do_another_handler,
        # Add more command handlers...
    }
```

#### 7. **Master Command Handler**

```python
async def _master_command_handler(self, topic: str, message: Dict[str, Any]):
    """
    Master command handler that dispatches to specific handlers.
    """
    try:
        # Validate handlers are initialized
        if self._command_handlers is None:
            logger.warning("Command handlers not initialized")
            return
        
        # Validate organization ID available
        if self._mqtt_proxy.organization_id is None:
            logger.warning("Organization ID not available")
            return
        
        # Extract command from message
        command = message.get("command", "")
        message_id = message.get("messageId", "unknown")
        wait_response = message.get("waitResponse", False)
        
        logger.info(f"📨 Received command: {command} (ID: {message_id})")
        
        # Route to specific handler
        handler = self._command_handlers.get(command)
        if handler:
            await handler(topic, message)
        else:
            logger.warning(f"Unknown command: {command}")
            
            if wait_response:
                await self._mqtt_proxy.send_command_response(
                    message_id,
                    {
                        "success": False,
                        "error": f"Unknown command: {command}"
                    }
                )
                
    except Exception as e:
        logger.error(f"Error in master command handler: {e}")
```

#### 8. **Specific Command Handlers**

```python
async def _do_something_handler(self, topic: str, message: Dict[str, Any]):
    """Handle specific command."""
    try:
        message_id = message.get("messageId", "unknown")
        data = message.get("data", {})
        wait_response = message.get("waitResponse", False)
        
        # Process command
        result = await self._process_something(data)
        
        # Send response if requested
        if wait_response:
            await self._mqtt_proxy.send_command_response(
                message_id,
                {
                    "success": True,
                    "data": result
                }
            )
            
    except Exception as e:
        logger.error(f"Error in do_something handler: {e}")
        
        if message.get("waitResponse", False):
            await self._mqtt_proxy.send_command_response(
                message.get("messageId", "unknown"),
                {
                    "success": False,
                    "error": str(e)
                }
            )
```

---

## Step-by-Step Implementation Guide

### Step 1: Add Class Attribute

```python
class FlightLogPetal(Petal):
    name = "flight-log-petal"
    version = "1.0.0"
    use_mqtt_proxy = True  # ← Add this
```

### Step 2: Initialize MQTT-Related Attributes

```python
def __init__(self):
    super().__init__()
    self._mqtt_proxy = None
    self._loop = None
    self._command_handlers = None
    self.mqtt_subscription_id = None
```

### Step 3: Store MQTT Proxy Reference in Startup

```python
def startup(self) -> None:
    super().startup()
    self._mqtt_proxy = self._proxies.get("mqtt")
```

### Step 4: Implement `_setup_mqtt_topics()`

```python
async def _setup_mqtt_topics(self):
    """Called by main app when organization ID is available."""
    self._command_handlers = self._setup_command_handlers()
    
    self.mqtt_subscription_id = self._mqtt_proxy.register_handler(
        self._master_command_handler
    )
    
    logger.info(f"MQTT setup completed for {self.name}")
```

### Step 5: Define Command Handlers Registry

```python
def _setup_command_handlers(self) -> Dict[str, Callable]:
    return {
        "flight-log/fetch_records": self._fetch_records_handler,
        "flight-log/upload_record": self._upload_record_handler,
    }
```

### Step 6: Implement Master Handler

```python
async def _master_command_handler(self, topic: str, message: Dict[str, Any]):
    if self._command_handlers is None:
        logger.warning("Handlers not initialized")
        return
    
    command = message.get("command", "")
    handler = self._command_handlers.get(command)
    
    if handler:
        await handler(topic, message)
    else:
        logger.warning(f"Unknown command: {command}")
```

### Step 7: Implement Specific Handlers

```python
async def _fetch_records_handler(self, topic: str, message: Dict[str, Any]):
    try:
        data = message.get("data", {})
        # Process request...
        
        await self._mqtt_proxy.send_command_response(
            message.get("messageId", "unknown"),
            {"success": True, "records": [...]}
        )
    except Exception as e:
        logger.error(f"Error: {e}")
```

---

## Complete Example

```python
from typing import Dict, Any, List, Callable
from petal_app_manager.plugins.base import Petal
from petal_app_manager.proxies import MQTTProxy
from . import logger

class ExamplePetal(Petal):
    name = "example-petal"
    version = "1.0.0"
    use_mqtt_proxy = True  # Enable MQTT-aware startup
    
    def __init__(self):
        super().__init__()
        self._mqtt_proxy = None
        self._loop = None
        self._command_handlers = None
        self.mqtt_subscription_id = None
    
    def startup(self) -> None:
        """Sync startup."""
        super().startup()
        self._mqtt_proxy = self._proxies.get("mqtt")
    
    async def async_startup(self) -> None:
        """
        Async startup - intentionally simple.
        Main app handles MQTT setup via _setup_mqtt_topics().
        """
        logger.info(f"{self.name} async_startup completed")
    
    async def _setup_mqtt_topics(self):
        """Setup MQTT - called by main app when org ID is available."""
        # Initialize command handlers
        self._command_handlers = self._setup_command_handlers()
        
        # Register master handler
        self.mqtt_subscription_id = self._mqtt_proxy.register_handler(
            self._master_command_handler
        )
        
        if self.mqtt_subscription_id:
            logger.info(f"✅ MQTT registered for {self.name}")
        else:
            logger.error(f"❌ Failed to register MQTT for {self.name}")
    
    def _setup_command_handlers(self) -> Dict[str, Callable]:
        """Map commands to handlers."""
        return {
            "example-petal/hello": self._hello_handler,
            "example-petal/process": self._process_handler,
        }
    
    async def _master_command_handler(self, topic: str, message: Dict[str, Any]):
        """Route commands to specific handlers."""
        try:
            if self._command_handlers is None:
                logger.warning("Handlers not initialized")
                return
            
            command = message.get("command", "")
            message_id = message.get("messageId", "unknown")
            
            logger.info(f"📨 Command: {command} (ID: {message_id})")
            
            handler = self._command_handlers.get(command)
            if handler:
                await handler(topic, message)
            else:
                logger.warning(f"⚠️ Unknown command: {command}")
                
                if message.get("waitResponse", False):
                    await self._mqtt_proxy.send_command_response(
                        message_id,
                        {"success": False, "error": f"Unknown command: {command}"}
                    )
        except Exception as e:
            logger.error(f"❌ Master handler error: {e}")
    
    async def _hello_handler(self, topic: str, message: Dict[str, Any]):
        """Handle hello command."""
        try:
            message_id = message.get("messageId", "unknown")
            data = message.get("data", {})
            name = data.get("name", "World")
            
            logger.info(f"👋 Hello command received for: {name}")
            
            if message.get("waitResponse", False):
                await self._mqtt_proxy.send_command_response(
                    message_id,
                    {
                        "success": True,
                        "message": f"Hello, {name}!"
                    }
                )
        except Exception as e:
            logger.error(f"❌ Hello handler error: {e}")
    
    async def _process_handler(self, topic: str, message: Dict[str, Any]):
        """Handle process command."""
        try:
            message_id = message.get("messageId", "unknown")
            data = message.get("data", {})
            
            # Do some processing...
            result = {"processed": True, "data": data}
            
            if message.get("waitResponse", False):
                await self._mqtt_proxy.send_command_response(
                    message_id,
                    {"success": True, "result": result}
                )
        except Exception as e:
            logger.error(f"❌ Process handler error: {e}")
```

---

## Migration from Old Pattern

### Old Pattern (Before Refactor)

```python
# ❌ OLD - Don't use this anymore
async def async_startup(self):
    # Manual organization ID checking
    org_id = await self._wait_for_organization_id()
    
    if org_id:
        # Subscribe to topics manually
        await self._mqtt_proxy.subscribe_to_topic(
            "my-topic", 
            self._my_callback
        )
    else:
        # Start monitoring task
        asyncio.create_task(self._monitor_org_id())
```

### New Pattern (After Refactor)

```python
# ✅ NEW - Use this pattern
class MyPetal(Petal):
    use_mqtt_proxy = True  # Enable automatic MQTT setup
    
    async def _setup_mqtt_topics(self):
        """Called automatically when org ID is available."""
        self._command_handlers = self._setup_command_handlers()
        self.mqtt_subscription_id = self._mqtt_proxy.register_handler(
            self._master_command_handler
        )
```

### Key Differences

| Aspect | Old Pattern | New Pattern |
|--------|-------------|-------------|
| **Organization ID** | Manual checking/monitoring | Automatic monitoring by main app |
| **Subscriptions** | Multiple topic subscriptions | Single handler registration |
| **Message Routing** | Topic-based | Command-based |
| **Event Loop** | Manual setup | Auto-set by main app |
| **Startup Logic** | Complex async_startup | Simple _setup_mqtt_topics |

---

## Testing MQTT Commands

### Sending Test Commands

Use the MQTT API or MQTT client to send commands:

```json
{
  "command": "example-petal/hello",
  "messageId": "test-123",
  "waitResponse": true,
  "data": {
    "name": "Developer"
  },
  "timestamp": "2025-11-05T12:00:00Z"
}
```

### Expected Response

```json
{
  "messageId": "test-123",
  "timestamp": "2025-11-05T12:00:01Z",
  "success": true,
  "message": "Hello, Developer!"
}
```

### Creating Test Handlers

Add test handlers to your command registry for easy testing:

```python
def _setup_command_handlers(self) -> Dict[str, Callable]:
    return {
        # Production handlers
        "my-petal/production": self._production_handler,
        
        # Test handlers (optional, for development)
        "my-petal/test": self._test_handler,
    }

async def _test_handler(self, topic: str, message: Dict[str, Any]):
    """Test handler with predefined data."""
    if getattr(self, "_test_called", False):
        logger.warning("Test already called")
        return
    
    self._test_called = True
    
    # Use predefined test data
    test_data = {"test": "data"}
    
    # Override message and call real handler
    test_message = message.copy()
    test_message["data"] = test_data
    
    await self._production_handler(topic, test_message)
```

---

## Best Practices

### 1. **Always Check Handler Initialization**

```python
if self._command_handlers is None:
    logger.warning("Handlers not initialized")
    return
```

### 2. **Validate Organization ID**

```python
if self._mqtt_proxy.organization_id is None:
    logger.warning("Organization ID not available")
    return
```

### 3. **Use Proper Error Handling**

```python
try:
    # Handler logic
    result = await process_command(data)
    
    if wait_response:
        await self._mqtt_proxy.send_command_response(
            message_id,
            {"success": True, "result": result}
        )
except Exception as e:
    logger.error(f"Error: {e}")
    
    if message.get("waitResponse", False):
        await self._mqtt_proxy.send_command_response(
            message.get("messageId", "unknown"),
            {"success": False, "error": str(e)}
        )
```

### 4. **Use Descriptive Command Names**

```python
# ✅ Good - includes petal name
"flight-log/fetch_records"
"flight-log/upload_record"

# ❌ Bad - too generic
"fetch"
"upload"
```

### 5. **Log Important Events**

```python
logger.info(f"📨 Received: {command}")
logger.info(f"✅ Success: {result}")
logger.error(f"❌ Error: {error}")
logger.warning(f"⚠️ Warning: {warning}")
```

---

## Troubleshooting

### Issue: Handler Not Called

**Symptoms:** MQTT messages arrive but handler is not invoked

**Solution:**
1. Check `use_mqtt_proxy = True` is set on petal class
2. Verify `_setup_mqtt_topics()` was called (check logs)
3. Ensure command name matches exactly in handler registry
4. Check organization ID is available: `mqtt_proxy.organization_id`

### Issue: Organization ID Not Available

**Symptoms:** "_setup_mqtt_topics not called" or "org ID monitoring started"

**Solution:**
- Organization ID monitoring is normal on first startup
- Check `/opt/droneleaf/certs/perm/thing-parameters.json` exists
- Verify OrganizationManager is properly initialized
- Wait for organization ID to be fetched (usually ~10 seconds)

### Issue: Response Not Sent

**Symptoms:** Command processed but no response received

**Solution:**
1. Check `waitResponse: true` in request
2. Verify `send_command_response()` is called
3. Check message_id is correctly extracted
4. Look for errors in logs

---

## Summary

The refactored MQTT architecture provides:

✅ **Simpler petal code** - Just implement `_setup_mqtt_topics()` and handlers  
✅ **Automatic organization ID monitoring** - Handled by main app  
✅ **Command-based routing** - Clear handler registry  
✅ **Error resilience** - Proper error handling and logging  
✅ **Scalable** - Easy to add new commands  
✅ **Testable** - Support for test handlers  

By following this guide, you can easily integrate MQTT command handling into any petal with minimal boilerplate code.
