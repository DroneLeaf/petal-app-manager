# HEAR_FC Communication Integration Guide

This document provides guidance for integrating the HEAR_FC C++ application with the petal-app-manager's Redis-based two-way communication system.

## Overview

The communication system uses Redis as a message broker with the following components:

1. **Message Queues**: Reliable message delivery using Redis sorted sets (priority queues)
2. **Pub/Sub**: Real-time notifications for new messages
3. **Status Tracking**: Application status and message acknowledgments
4. **JSON Protocol**: Structured message format for interoperability

## Redis Data Structures

### Message Queues
- **Inbox Queue**: `queue:{app_id}:inbox` - Sorted set with priority-based ordering
- **Outbox Queue**: `queue:{app_id}:outbox` - For debugging and monitoring

### Status Tracking
- **Application Status**: `status:{app_id}` - Hash with status information
- **Message Metadata**: `message:{message_id}` - Hash with message processing status

### Pub/Sub Channels
- **Application Channel**: `channel:{app_id}` - Direct notifications to specific app
- **Broadcast Channel**: `channel:broadcast` - System-wide notifications

## Message Format

All messages use JSON format with the following structure:

```json
{
  "id": "unique-message-id",
  "sender": "sending-app-id",
  "recipient": "receiving-app-id", 
  "message_type": "command|telemetry|status|alert|etc",
  "payload": {
    "command": "takeoff",
    "parameters": {"altitude": 20},
    "other_data": "..."
  },
  "priority": 1-4,
  "timestamp": 1234567890.123,
  "reply_to": "original-message-id",
  "timeout": 30
}
```

## Priority Levels
- `1`: LOW
- `2`: NORMAL  
- `3`: HIGH
- `4`: CRITICAL

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
        
        // Connect to Redis
        redis_ctx = redisConnect("127.0.0.1", 6379);
        pubsub_ctx = redisConnect("127.0.0.1", 6379);
        
        if (redis_ctx->err || pubsub_ctx->err) {
            throw std::runtime_error("Redis connection failed");
        }
        
        // Set application status as online
        setStatus("online");
    }
    
    ~HearFCCommunicator() {
        stopListening();
        setStatus("offline");
        redisFree(redis_ctx);
        redisFree(pubsub_ctx);
    }
    
    void setStatus(const std::string& status) {
        redisReply* reply = (redisReply*)redisCommand(redis_ctx,
            "HSET status:%s status %s last_seen %f app_id %s",
            app_id.c_str(), status.c_str(), 
            std::chrono::duration<double>(
                std::chrono::system_clock::now().time_since_epoch()
            ).count(),
            app_id.c_str());
        freeReplyObject(reply);
    }
};
```

### Message Sending (C++)

```cpp
bool HearFCCommunicator::sendMessage(
    const std::string& recipient,
    const std::string& message_type,
    const Json::Value& payload,
    int priority = 2) {
    
    // Create message JSON
    Json::Value message;
    message["id"] = generateMessageId();
    message["sender"] = app_id;
    message["recipient"] = recipient;
    message["message_type"] = message_type;
    message["payload"] = payload;
    message["priority"] = priority;
    message["timestamp"] = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    
    // Serialize to string
    Json::StreamWriterBuilder builder;
    std::string message_str = Json::writeString(builder, message);
    
    // Calculate priority score
    double priority_score = priority * 1000 + message["timestamp"].asDouble();
    
    // Add to recipient's inbox queue
    std::string queue_name = "queue:" + recipient + ":inbox";
    redisReply* reply = (redisReply*)redisCommand(redis_ctx,
        "ZADD %s %f %s",
        queue_name.c_str(), priority_score, message_str.c_str());
    
    bool success = (reply && reply->integer == 1);
    freeReplyObject(reply);
    
    if (success) {
        // Send notification
        std::string channel = "channel:" + recipient;
        reply = (redisReply*)redisCommand(redis_ctx,
            "PUBLISH %s new_message:%s",
            channel.c_str(), message["id"].asString().c_str());
        freeReplyObject(reply);
        
        // Store message metadata
        std::string meta_key = "message:" + message["id"].asString();
        reply = (redisReply*)redisCommand(redis_ctx,
            "HSET %s status pending sender %s recipient %s timestamp %f type %s",
            meta_key.c_str(), app_id.c_str(), recipient.c_str(),
            message["timestamp"].asDouble(), message_type.c_str());
        freeReplyObject(reply);
    }
    
    return success;
}
```

### Message Receiving (C++)

```cpp
void HearFCCommunicator::startListening() {
    if (is_listening) return;
    
    is_listening = true;
    listener_thread = std::thread(&HearFCCommunicator::messageLoop, this);
}

void HearFCCommunicator::messageLoop() {
    std::string inbox_queue = "queue:" + app_id + ":inbox";
    
    while (is_listening) {
        // Check for new messages with timeout
        redisReply* reply = (redisReply*)redisCommand(redis_ctx,
            "ZPOPMAX %s 1", inbox_queue.c_str());
        
        if (reply && reply->type == REDIS_REPLY_ARRAY && reply->elements > 0) {
            // Parse message
            std::string message_str = reply->element[0]->element[0]->str;
            double priority_score = reply->element[0]->element[1]->dval;
            
            Json::Value message;
            Json::Reader reader;
            if (reader.parse(message_str, message)) {
                handleMessage(message);
            }
        }
        freeReplyObject(reply);
        
        // Small delay to prevent CPU spinning
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

void HearFCCommunicator::handleMessage(const Json::Value& message) {
    std::string message_type = message["message_type"].asString();
    std::string message_id = message["id"].asString();
    
    // Update message status
    std::string meta_key = "message:" + message_id;
    redisReply* reply = (redisReply*)redisCommand(redis_ctx,
        "HSET %s status processing", meta_key.c_str());
    freeReplyObject(reply);
    
    try {
        // Handle different message types
        if (message_type == "command") {
            handleCommand(message);
        } else if (message_type == "configuration") {
            handleConfiguration(message);
        } else if (message_type == "telemetry_request") {
            handleTelemetryRequest(message);
        } else if (message_type == "health_check") {
            handleHealthCheck(message);
        }
        
        // Mark as completed
        reply = (redisReply*)redisCommand(redis_ctx,
            "HSET %s status completed", meta_key.c_str());
        freeReplyObject(reply);
        
    } catch (const std::exception& e) {
        // Mark as failed
        reply = (redisReply*)redisCommand(redis_ctx,
            "HSET %s status failed", meta_key.c_str());
        freeReplyObject(reply);
        
        std::cerr << "Error handling message: " << e.what() << std::endl;
    }
}
```

### Command Handling Example (C++)

```cpp
void HearFCCommunicator::handleCommand(const Json::Value& message) {
    Json::Value payload = message["payload"];
    std::string command = payload["command"].asString();
    std::string command_id = payload["command_id"].asString();
    
    Json::Value response_payload;
    response_payload["command_id"] = command_id;
    response_payload["command"] = command;
    
    try {
        if (command == "takeoff") {
            double altitude = payload["parameters"]["altitude"].asDouble();
            bool success = executeTakeoff(altitude);
            
            response_payload["status"] = success ? "success" : "failed";
            response_payload["message"] = success ? 
                "Takeoff completed" : "Takeoff failed";
            
        } else if (command == "land") {
            bool precision = payload["parameters"]["precision"].asBool();
            bool success = executeLand(precision);
            
            response_payload["status"] = success ? "success" : "failed";
            response_payload["message"] = success ? 
                "Landing completed" : "Landing failed";
                
        } else if (command == "goto") {
            double lat = payload["parameters"]["lat"].asDouble();
            double lon = payload["parameters"]["lon"].asDouble(); 
            double alt = payload["parameters"]["altitude"].asDouble();
            
            bool success = executeGoto(lat, lon, alt);
            response_payload["status"] = success ? "success" : "failed";
            
        } else {
            response_payload["status"] = "error";
            response_payload["message"] = "Unknown command: " + command;
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
}

// Call this periodically (e.g., 1Hz)
void HearFCCommunicator::telemetryLoop() {
    while (is_running) {
        broadcastTelemetry();
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
```

## Message Types and Protocols

### Commands (petal-app-manager → HEAR_FC)
```json
{
  "message_type": "command",
  "payload": {
    "command_id": "cmd_1234567890",
    "command": "takeoff|land|goto|hover|emergency_stop",
    "parameters": {
      "altitude": 20,
      "lat": 37.7749,
      "lon": -122.4194
    }
  }
}
```

### Telemetry (HEAR_FC → petal-app-manager)
```json
{
  "message_type": "telemetry", 
  "payload": {
    "timestamp": 1234567890.123,
    "battery_level": 85,
    "gps_coordinates": {"lat": 37.7749, "lon": -122.4194},
    "altitude": 50.5,
    "speed": 5.2,
    "orientation": {"roll": 0.1, "pitch": 0.2, "yaw": 45.0},
    "system_status": "normal|warning|error"
  }
}
```

### Configuration (petal-app-manager → HEAR_FC)
```json
{
  "message_type": "configuration",
  "payload": {
    "flight_mode": "autonomous|manual|guided",
    "max_altitude": 100,
    "max_speed": 10,
    "geofence": {
      "enabled": true,
      "center": {"lat": 37.7749, "lon": -122.4194},
      "radius": 1000
    }
  }
}
```

### Alerts (HEAR_FC → petal-app-manager)
```json
{
  "message_type": "alert",
  "payload": {
    "severity": "info|warning|critical",
    "message": "Low battery warning",
    "details": {"battery_level": 15, "estimated_flight_time": 120}
  }
}
```

## Testing the Integration

### Redis CLI Commands for Testing

```bash
# Check if HEAR_FC is online
redis-cli HGETALL status:HEAR_FC

# Send test command to HEAR_FC
redis-cli ZADD queue:HEAR_FC:inbox 3000 '{"id":"test1","sender":"test","recipient":"HEAR_FC","message_type":"command","payload":{"command":"status"},"priority":3,"timestamp":1234567890}'

# Check message status
redis-cli HGETALL message:test1

# Monitor messages (in separate terminal)
redis-cli MONITOR
```

### Integration Testing Steps

1. **Start Redis server**: `redis-server`
2. **Start HEAR_FC application** with communication enabled
3. **Start petal-app-manager** communication example
4. **Verify connectivity** using status checks
5. **Test message exchange** with simple commands
6. **Monitor telemetry flow** for expected data
7. **Test error handling** with invalid commands

## Best Practices

1. **Always acknowledge receipt** of critical commands
2. **Use appropriate priority levels** for different message types
3. **Implement proper error handling** and status reporting
4. **Monitor Redis connection health** and reconnect if needed
5. **Use message timeouts** for time-sensitive operations
6. **Validate all incoming message data** before processing
7. **Implement graceful shutdown** with status updates

## Troubleshooting

### Common Issues

1. **Redis connection failures**: Check Redis server status and network connectivity
2. **Message not received**: Verify queue names and Redis key patterns
3. **JSON parsing errors**: Validate message format and encoding
4. **Priority ordering issues**: Check priority score calculation
5. **Memory leaks**: Ensure proper Redis reply object cleanup

### Debug Commands

```bash
# List all keys
redis-cli KEYS "*"

# Monitor real-time commands
redis-cli MONITOR

# Check queue contents
redis-cli ZRANGE queue:HEAR_FC:inbox 0 -1 WITHSCORES

# Check application status
redis-cli HGETALL status:HEAR_FC
```

This integration guide provides the foundation for implementing robust two-way communication between petal-app-manager and HEAR_FC using Redis as the message broker.
