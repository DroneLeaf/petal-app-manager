# HEAR_FC Communication Integration Guide

This document provides guidance for integrating the HEAR_FC C++ application with the petal-app-manager using Redis pub/sub for real-time communication.

## Overview

The communication system uses Redis pub/sub channels for simple, real-time message exchange:

1. **Pub/Sub Channels**: Direct message publishing and subscription
2. **JSON Messages**: Structured message format for interoperability  
3. **Key-Value Storage**: Optional data persistence using Redis keys
4. **Unix Socket Support**: High-performance local communication

## Redis Communication Pattern

### Pub/Sub Channels
- **HEAR_FC Commands**: `hear_fc_commands` - Commands sent to HEAR_FC
- **HEAR_FC Telemetry**: `hear_fc_telemetry` - Telemetry data from HEAR_FC
- **HEAR_FC Status**: `hear_fc_status` - Status updates from HEAR_FC
- **HEAR_FC Responses**: `hear_fc_responses` - Command responses from HEAR_FC

### Key-Value Storage (Optional)
- **Configuration**: `hear_fc:config` - HEAR_FC configuration data
- **Latest Status**: `hear_fc:latest_status` - Most recent status for persistence
- **Latest Telemetry**: `hear_fc:latest_telemetry` - Most recent telemetry data

## Message Format

All messages use simple JSON format:

```json
{
  "timestamp": 1234567890.123,
  "message_type": "command|telemetry|status|response",
  "data": {
    "command": "takeoff",
    "parameters": {"altitude": 20},
    "other_data": "..."
  }
}
```

## Message Types
- **command**: Commands sent to HEAR_FC (takeoff, land, goto, etc.)
- **telemetry**: Real-time flight data from HEAR_FC
- **status**: System status updates from HEAR_FC  
- **response**: Command execution results from HEAR_FC

## C++ Implementation Guide

### Dependencies
```bash
# Install required libraries
sudo apt-get install libhiredis-dev libjsoncpp-dev
```

### Basic Redis Connection (C++)

```cpp
#include <hiredis/hiredis.h>
#include <json/json.h>
#include <string>
#include <thread>
#include <chrono>
#include <iostream>

class HearFCCommunicator {
private:
    redisContext* redis_ctx;
    redisContext* pubsub_ctx;
    std::string app_id;
    bool is_listening;
    std::thread listener_thread;

public:
    HearFCCommunicator(const std::string& app_id = "HEAR_FC") 
        : app_id(app_id), is_listening(false) {
        
        // Connect to Redis (try Unix socket first, fallback to TCP)
        redis_ctx = redisConnectUnix("/tmp/redis.sock");
        if (redis_ctx->err) {
            redisFree(redis_ctx);
            redis_ctx = redisConnect("127.0.0.1", 6379);
        }
        
        pubsub_ctx = redisConnectUnix("/tmp/redis.sock");
        if (pubsub_ctx->err) {
            redisFree(pubsub_ctx);
            pubsub_ctx = redisConnect("127.0.0.1", 6379);
        }
        
        if (redis_ctx->err || pubsub_ctx->err) {
            throw std::runtime_error("Redis connection failed");
        }
        
        // Store initial status
        storeStatus("online");
    }
    
    ~HearFCCommunicator() {
        stopListening();
        storeStatus("offline");
        redisFree(redis_ctx);
        redisFree(pubsub_ctx);
    }
    
    void storeStatus(const std::string& status) {
        Json::Value status_data;
        status_data["status"] = status;
        status_data["timestamp"] = std::chrono::duration<double>(
            std::chrono::system_clock::now().time_since_epoch()
        ).count();
        status_data["app_id"] = app_id;
        
        Json::StreamWriterBuilder builder;
        std::string status_str = Json::writeString(builder, status_data);
        
        // Store in Redis key for persistence
        redisReply* reply = (redisReply*)redisCommand(redis_ctx,
            "SET hear_fc:latest_status %s", status_str.c_str());
        freeReplyObject(reply);
        
        // Also publish status update
        publishStatus(status);
    }
};
```

### Publishing Messages (C++)

```cpp
bool HearFCCommunicator::publishMessage(
    const std::string& channel,
    const std::string& message_type,
    const Json::Value& data) {
    
    // Create message JSON
    Json::Value message;
    message["timestamp"] = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    message["message_type"] = message_type;
    message["data"] = data;
    
    // Serialize to string
    Json::StreamWriterBuilder builder;
    std::string message_str = Json::writeString(builder, message);
    
    // Publish to channel
    redisReply* reply = (redisReply*)redisCommand(redis_ctx,
        "PUBLISH %s %s", channel.c_str(), message_str.c_str());
    
    bool success = (reply && reply->type == REDIS_REPLY_INTEGER);
    int subscriber_count = success ? reply->integer : 0;
    freeReplyObject(reply);
    
    if (success) {
        std::cout << "Published to " << channel << " (" 
                  << subscriber_count << " subscribers)" << std::endl;
    }
    
    return success;
}

// Convenience methods for specific message types
void HearFCCommunicator::publishTelemetry(const Json::Value& telemetry_data) {
    publishMessage("hear_fc_telemetry", "telemetry", telemetry_data);
    
    // Also store latest telemetry for persistence
    Json::StreamWriterBuilder builder;
    std::string telemetry_str = Json::writeString(builder, telemetry_data);
    redisReply* reply = (redisReply*)redisCommand(redis_ctx,
        "SET hear_fc:latest_telemetry %s", telemetry_str.c_str());
    freeReplyObject(reply);
}

void HearFCCommunicator::publishStatus(const std::string& status) {
    Json::Value status_data;
    status_data["status"] = status;
    status_data["app_id"] = app_id;
    publishMessage("hear_fc_status", "status", status_data);
}

void HearFCCommunicator::publishResponse(const std::string& command_id, 
                                        const std::string& result,
                                        const std::string& message = "") {
    Json::Value response_data;
    response_data["command_id"] = command_id;
    response_data["result"] = result;  // "success", "failed", "error"
    response_data["message"] = message;
    publishMessage("hear_fc_responses", "response", response_data);
}
    
    bool success = (reply && reply->integer == 1);
    freeReplyObject(reply);
    
    if (success) {
        // Send notification
        std::string channel = "channel:" + recipient;
### Subscribing to Messages (C++)

```cpp
void HearFCCommunicator::startListening() {
    if (is_listening) return;
    
    is_listening = true;
    listener_thread = std::thread(&HearFCCommunicator::subscriptionLoop, this);
}

void HearFCCommunicator::subscriptionLoop() {
    // Subscribe to command channel
    redisReply* reply = (redisReply*)redisCommand(pubsub_ctx,
        "SUBSCRIBE hear_fc_commands");
    freeReplyObject(reply);
    
    while (is_listening) {
        // Wait for messages
        reply = (redisReply*)redisCommand(pubsub_ctx, "BLPOP temp 1");
        if (reply) {
            freeReplyObject(reply);
        }
        
        // Check for pub/sub messages
        reply = nullptr;
        if (redisGetReply(pubsub_ctx, (void**)&reply) == REDIS_OK && reply) {
            if (reply->type == REDIS_REPLY_ARRAY && reply->elements == 3) {
                std::string message_type = reply->element[0]->str;
                std::string channel = reply->element[1]->str;
                std::string message_content = reply->element[2]->str;
                
                if (message_type == "message") {
                    handleSubscribedMessage(channel, message_content);
                }
            }
            freeReplyObject(reply);
        }
        
        // Small delay to prevent CPU spinning
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

void HearFCCommunicator::handleSubscribedMessage(
    const std::string& channel, 
    const std::string& message_content) {
    
    Json::Value message;
    Json::Reader reader;
    
    if (!reader.parse(message_content, message)) {
        std::cerr << "Failed to parse message JSON" << std::endl;
        return;
    }
    
    std::string message_type = message["message_type"].asString();
    Json::Value data = message["data"];
    
    try {
        if (channel == "hear_fc_commands" && message_type == "command") {
            handleCommand(data);
        } else {
            std::cout << "Received message on " << channel 
                     << " type: " << message_type << std::endl;
        }
    } catch (const std::exception& e) {
        std::cerr << "Error handling message: " << e.what() << std::endl;
    }
}
    }
}

void HearFCCommunicator::handleMessage(const Json::Value& message) {
    std::string message_type = message["message_type"].asString();
    std::string message_id = message["id"].asString();
    
    // Update message status
    std::string meta_key = "message:" + message_id;
    redisReply* reply = (redisReply*)redisCommand(redis_ctx,
        "HSET %s status processing", meta_key.c_str());
### Command Handling Example (C++)

```cpp
void HearFCCommunicator::handleCommand(const Json::Value& data) {
    std::string command = data["command"].asString();
    std::string command_id = data.get("command_id", "").asString();
    Json::Value parameters = data["parameters"];
    
    std::string result = "success";
    std::string message = "";
    
    try {
        if (command == "takeoff") {
            double altitude = parameters["altitude"].asDouble();
            bool success = executeTakeoff(altitude);
            
            result = success ? "success" : "failed";
            message = success ? "Takeoff completed" : "Takeoff failed";
            
        } else if (command == "land") {
            bool precision = parameters.get("precision", false).asBool();
            bool success = executeLand(precision);
            
            result = success ? "success" : "failed";
            message = success ? "Landing completed" : "Landing failed";
                
        } else if (command == "goto") {
            double lat = parameters["lat"].asDouble();
            double lon = parameters["lon"].asDouble(); 
            double alt = parameters["altitude"].asDouble();
            
            bool success = executeGoto(lat, lon, alt);
            result = success ? "success" : "failed";
            message = success ? "Navigation completed" : "Navigation failed";
            
        } else if (command == "hover") {
            bool success = executeHover();
            result = success ? "success" : "failed";
            message = success ? "Hover mode activated" : "Hover failed";
            
        } else if (command == "emergency_stop") {
            bool success = executeEmergencyStop();
            result = success ? "success" : "failed";
            message = success ? "Emergency stop executed" : "Emergency stop failed";
            
        } else {
            result = "error";
            message = "Unknown command: " + command;
        }
        
    } catch (const std::exception& e) {
        result = "error";
        message = std::string("Command execution error: ") + e.what();
    }
    
    // Send response back
    if (!command_id.empty()) {
        publishResponse(command_id, result, message);
    }
}
        
    } catch (const std::exception& e) {
        response_payload["status"] = "error";
        response_payload["message"] = std::string("Command execution error: ") + e.what();
    }
    
    // Send response back to sender
    sendMessage(message["sender"].asString(), "command_response", response_payload, 3);
}
```

### Telemetry Broadcasting (C++)

```cpp
void HearFCCommunicator::broadcastTelemetry() {
    Json::Value telemetry;
    telemetry["timestamp"] = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    
    // Gather telemetry data
    telemetry["battery_level"] = getBatteryLevel();
    telemetry["gps_coordinates"] = getGPSCoordinates();
    telemetry["altitude"] = getCurrentAltitude();
    telemetry["speed"] = getCurrentSpeed();
    telemetry["orientation"] = getOrientation();
    telemetry["system_status"] = getSystemStatus();
    
    // Send to petal-app-manager
    sendMessage("petal-app-manager", "telemetry", telemetry, 2);
### Telemetry Broadcasting (C++)

```cpp
void HearFCCommunicator::broadcastTelemetry() {
    Json::Value telemetry_data;
    telemetry_data["timestamp"] = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    
    // Gather telemetry data from your flight controller
    telemetry_data["battery_level"] = getBatteryLevel();
    telemetry_data["gps_coordinates"]["lat"] = getLatitude();
    telemetry_data["gps_coordinates"]["lon"] = getLongitude();
    telemetry_data["altitude"] = getCurrentAltitude();
    telemetry_data["speed"] = getCurrentSpeed();
    telemetry_data["orientation"]["roll"] = getRoll();
    telemetry_data["orientation"]["pitch"] = getPitch();
    telemetry_data["orientation"]["yaw"] = getYaw();
    telemetry_data["system_status"] = getSystemStatus(); // "normal", "warning", "error"
    
    // Publish telemetry
    publishTelemetry(telemetry_data);
}

// Call this periodically (e.g., 1Hz)
void HearFCCommunicator::telemetryLoop() {
    while (is_running) {
        broadcastTelemetry();
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}

void HearFCCommunicator::stopListening() {
    is_listening = false;
    if (listener_thread.joinable()) {
        listener_thread.join();
    }
}
```

## Message Types and Examples

### Commands (petal-app-manager → HEAR_FC)
Published to: `hear_fc_commands`

```json
{
  "timestamp": 1234567890.123,
  "message_type": "command",
  "data": {
    "command_id": "cmd_1234567890",
    "command": "takeoff",
    "parameters": {
      "altitude": 20
    }
  }
}
```

#### Supported Commands:
- **takeoff**: `{"command": "takeoff", "parameters": {"altitude": 20}}`
- **land**: `{"command": "land", "parameters": {"precision": true}}`
- **goto**: `{"command": "goto", "parameters": {"lat": 37.7749, "lon": -122.4194, "altitude": 50}}`
- **hover**: `{"command": "hover", "parameters": {}}`
- **emergency_stop**: `{"command": "emergency_stop", "parameters": {}}`

### Telemetry (HEAR_FC → petal-app-manager)
Published to: `hear_fc_telemetry`

```json
{
  "timestamp": 1234567890.123,
  "message_type": "telemetry",
  "data": {
    "battery_level": 85,
    "gps_coordinates": {"lat": 37.7749, "lon": -122.4194},
    "altitude": 50.5,
    "speed": 5.2,
    "orientation": {"roll": 0.1, "pitch": 0.2, "yaw": 45.0},
    "system_status": "normal"
  }
}
```

### Status Updates (HEAR_FC → petal-app-manager)
Published to: `hear_fc_status`

```json
{
  "timestamp": 1234567890.123,
  "message_type": "status", 
  "data": {
    "status": "online",
    "app_id": "HEAR_FC"
  }
}
```

## Petal-App-Manager Integration

The petal-app-manager side can easily communicate with HEAR_FC using the Redis proxy:

```python
from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import http_endpoint
import json

class DroneControlPetal(Petal):
    def __init__(self):
        super().__init__()
        self.name = "drone_control"
    
    def startup(self):
        super().startup()
        asyncio.create_task(self._setup_subscriptions())
    
    async def _setup_subscriptions(self):
        redis = self.proxies["redis"]
        await redis.subscribe("hear_fc_telemetry", self._handle_telemetry)
        await redis.subscribe("hear_fc_status", self._handle_status)
        await redis.subscribe("hear_fc_responses", self._handle_responses)
    
    async def _handle_telemetry(self, channel: str, message: str):
        try:
            data = json.loads(message)
            telemetry = data["data"]
            self.log.info(f"Telemetry: Battery {telemetry['battery_level']}%")
            # Process telemetry data...
        except Exception as e:
            self.log.error(f"Error processing telemetry: {e}")
    
    async def _handle_status(self, channel: str, message: str):
        try:
            data = json.loads(message)
            status = data["data"]["status"]
            self.log.info(f"HEAR_FC Status: {status}")
        except Exception as e:
            self.log.error(f"Error processing status: {e}")
    
    async def _handle_responses(self, channel: str, message: str):
        try:
            data = json.loads(message)
            response = data["data"]
            self.log.info(f"Command {response['command_id']}: {response['result']}")
        except Exception as e:
            self.log.error(f"Error processing response: {e}")
    
    @http_endpoint(path="/takeoff", method="POST")
    async def takeoff(self, request):
        data = await request.json()
        altitude = data.get("altitude", 20)
        
        command = {
            "timestamp": time.time(),
            "message_type": "command",
            "data": {
                "command_id": f"cmd_{int(time.time())}",
                "command": "takeoff",
                "parameters": {"altitude": altitude}
            }
        }
        
        redis = self.proxies["redis"]
        count = await redis.publish("hear_fc_commands", json.dumps(command))
        
        return {"sent": count > 0, "subscribers": count}
```

## Testing the Integration

### Redis CLI Commands for Testing

```bash
# Check latest status
redis-cli GET hear_fc:latest_status

# Check latest telemetry  
redis-cli GET hear_fc:latest_telemetry

# Send test command to HEAR_FC
redis-cli PUBLISH hear_fc_commands '{"timestamp":1234567890,"message_type":"command","data":{"command_id":"test1","command":"hover","parameters":{}}}'

# Monitor all pub/sub messages
redis-cli PSUBSCRIBE "*"

# Monitor specific channels
redis-cli SUBSCRIBE hear_fc_telemetry hear_fc_status hear_fc_responses
```

### Integration Testing Steps

1. **Start Redis server**: `redis-server --unixsocket /tmp/redis.sock`
2. **Start HEAR_FC application** with pub/sub communication enabled
3. **Start petal-app-manager** with Redis proxy configured
4. **Verify connectivity** by checking status messages
5. **Test command sending** from petal endpoints
6. **Monitor telemetry flow** for expected data rates
7. **Test error handling** with invalid commands

## Best Practices

1. **Use Unix sockets** when possible for better performance
2. **Handle JSON parsing errors** gracefully 
3. **Implement proper error handling** in command execution
4. **Monitor Redis connection health** and reconnect if needed
5. **Use appropriate telemetry rates** (1Hz is usually sufficient)
6. **Validate all incoming command data** before execution
7. **Implement graceful shutdown** with status updates
8. **Store critical data** in Redis keys for persistence

## Troubleshooting

### Common Issues

1. **Redis connection failures**: Check Redis server status and socket/port accessibility
2. **Messages not received**: Verify channel names and subscription setup
3. **JSON parsing errors**: Validate message format and encoding
4. **No subscribers**: Check if petal-app-manager is running and subscribed
5. **Command execution failures**: Check HEAR_FC flight controller interface

### Debug Commands

```bash
# List all Redis keys
redis-cli KEYS "*"

# Monitor real-time commands
redis-cli MONITOR

# Check active subscribers per channel
redis-cli PUBSUB CHANNELS
redis-cli PUBSUB NUMSUB hear_fc_commands

# Check Redis info
redis-cli INFO
```

### Debugging Tips

1. **Use Redis MONITOR** to see all commands in real-time
2. **Check both TCP and Unix socket** connections
3. **Validate JSON** using online tools or `jq` command
4. **Test with Redis CLI** before implementing in C++
5. **Use logging** extensively in both HEAR_FC and petal sides

This simplified pub/sub approach provides real-time communication without the complexity of message queues, while still maintaining reliability through Redis persistence for critical data.
