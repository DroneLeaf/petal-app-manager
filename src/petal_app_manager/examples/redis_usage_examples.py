"""
Simple usage examples for the cleaned Redis proxy.

This shows how to use the Redis proxy for basic pub/sub and key-value operations
with Unix socket support.
"""

import asyncio
import json
from petal_app_manager.proxies.redis import RedisProxy


async def publisher_example():
    """Example of publishing messages to Redis channels."""
    
    # Create proxy with Unix socket (or use host/port for TCP)
    proxy = RedisProxy(
        unix_socket_path="/tmp/redis.sock",  # Use your Redis Unix socket path
        # Or use TCP connection:
        # host="localhost",
        # port=6379,
        db=0
    )
    
    try:
        # Start the proxy
        await proxy.start()
        print("✓ Redis proxy started")
        
        # Publish some messages
        messages = [
            {"type": "notification", "message": "System startup complete"},
            {"type": "alert", "level": "info", "message": "All services online"},
            {"type": "data", "sensor": "temperature", "value": 23.5}
        ]
        
        for msg in messages:
            # Publish to different channels
            if msg["type"] == "notification":
                count = await proxy.publish("notifications", json.dumps(msg))
                print(f"✓ Published notification to {count} subscribers")
                
            elif msg["type"] == "alert":
                count = await proxy.publish("alerts", json.dumps(msg))
                print(f"✓ Published alert to {count} subscribers")
                
            elif msg["type"] == "data":
                count = await proxy.publish("sensor_data", json.dumps(msg))
                print(f"✓ Published sensor data to {count} subscribers")
            
            await asyncio.sleep(1)  # Wait between messages
            
    finally:
        # Clean up
        await proxy.stop()
        print("✓ Redis proxy stopped")


async def subscriber_example():
    """Example of subscribing to Redis channels."""
    
    proxy = RedisProxy(
        unix_socket_path="/tmp/redis.sock",  # Use your Redis Unix socket path
        db=0
    )
    
    # Define callback functions for different channels
    async def handle_notifications(channel: str, message: str):
        try:
            data = json.loads(message)
            print(f"📢 Notification: {data.get('message', message)}")
        except json.JSONDecodeError:
            print(f"📢 Notification (raw): {message}")
    
    async def handle_alerts(channel: str, message: str):
        try:
            data = json.loads(message)
            level = data.get('level', 'unknown')
            msg = data.get('message', message)
            print(f"🚨 Alert [{level.upper()}]: {msg}")
        except json.JSONDecodeError:
            print(f"🚨 Alert (raw): {message}")
    
    async def handle_sensor_data(channel: str, message: str):
        try:
            data = json.loads(message)
            sensor = data.get('sensor', 'unknown')
            value = data.get('value', 'N/A')
            print(f"📊 Sensor {sensor}: {value}")
        except json.JSONDecodeError:
            print(f"📊 Sensor data (raw): {message}")
    
    try:
        # Start the proxy
        await proxy.start()
        print("✓ Redis subscriber started")
        
        # Subscribe to channels
        await proxy.subscribe("notifications", handle_notifications)
        await proxy.subscribe("alerts", handle_alerts)
        await proxy.subscribe("sensor_data", handle_sensor_data)
        
        print("✓ Subscribed to channels: notifications, alerts, sensor_data")
        print("Listening for messages... (Ctrl+C to stop)")
        
        # Keep running to receive messages
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n✓ Stopping subscriber...")
            
    finally:
        # Clean up
        await proxy.stop()
        print("✓ Redis subscriber stopped")


async def key_value_example():
    """Example of using Redis for key-value storage."""
    
    proxy = RedisProxy(
        unix_socket_path="/tmp/redis.sock",  # Use your Redis Unix socket path
        db=0
    )
    
    try:
        # Start the proxy
        await proxy.start()
        print("✓ Redis proxy started")
        
        # Store some data
        await proxy.set("app:status", "running")
        await proxy.set("app:version", "1.0.0")
        await proxy.set("temp:session", "abc123", ex=300)  # Expires in 5 minutes
        
        print("✓ Stored application data")
        
        # Retrieve data
        status = await proxy.get("app:status")
        version = await proxy.get("app:version")
        session = await proxy.get("temp:session")
        
        print(f"App Status: {status}")
        print(f"App Version: {version}")
        print(f"Session ID: {session}")
        
        # Check if keys exist
        status_exists = await proxy.exists("app:status")
        nonexistent_exists = await proxy.exists("nonexistent:key")
        
        print(f"Status key exists: {status_exists}")
        print(f"Nonexistent key exists: {nonexistent_exists}")
        
        # Store some structured data as JSON
        user_data = {
            "id": 123,
            "name": "John Doe",
            "email": "john@example.com",
            "last_login": "2025-01-01T10:00:00Z"
        }
        
        await proxy.set("user:123", json.dumps(user_data))
        
        # Retrieve and parse JSON data
        stored_user = await proxy.get("user:123")
        if stored_user:
            user_obj = json.loads(stored_user)
            print(f"User: {user_obj['name']} ({user_obj['email']})")
        
        # Clean up test data
        await proxy.delete("app:status")
        await proxy.delete("app:version")
        await proxy.delete("user:123")
        
        print("✓ Cleaned up test data")
        
    finally:
        # Clean up
        await proxy.stop()
        print("✓ Redis proxy stopped")


async def main():
    """Run examples based on command line argument or interactively."""
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == "publish":
            await publisher_example()
        elif mode == "subscribe":
            await subscriber_example()
        elif mode == "kv":
            await key_value_example()
        else:
            print("Usage: python redis_usage_examples.py [publish|subscribe|kv]")
    else:
        # Interactive mode
        print("Redis Proxy Usage Examples")
        print("=========================")
        print()
        print("1. Key-Value operations")
        print("2. Publisher")
        print("3. Subscriber")
        print()
        
        try:
            choice = input("Choose an example (1-3): ").strip()
            
            if choice == "1":
                await key_value_example()
            elif choice == "2":
                await publisher_example()
            elif choice == "3":
                await subscriber_example()
            else:
                print("Invalid choice")
                
        except KeyboardInterrupt:
            print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
