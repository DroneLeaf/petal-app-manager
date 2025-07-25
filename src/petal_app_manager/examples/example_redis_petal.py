"""
Example Petal showing how to use the simplified Redis proxy for pub/sub and key-value operations.
"""

import asyncio
import json
from typing import Dict, Any
from fastapi import Request
from fastapi.responses import JSONResponse

from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import http_endpoint


class ExampleRedisPetal(Petal):
    """
    Example petal demonstrating Redis proxy usage.
    """
    
    def __init__(self):
        super().__init__()
        self.name = "redis_example"
        self.version = "1.0.0"
        self.redis_proxy = None
        
    def startup(self):
        """Called when the petal starts up."""
        super().startup()
        self.redis_proxy = self.proxies.get("redis")
        
        # Subscribe to a channel when the petal starts
        if self.redis_proxy:
            # Schedule the subscription for after the event loop is running
            asyncio.create_task(self._setup_subscriptions())
    
    async def _setup_subscriptions(self):
        """Set up Redis subscriptions."""
        try:
            # Subscribe to a general broadcast channel
            await self.redis_proxy.subscribe("notifications", self._handle_notification)
            
            # Subscribe to a specific channel for this petal
            await self.redis_proxy.subscribe("redis_example_commands", self._handle_command)
            
            self.log.info("Redis subscriptions set up successfully")
        except Exception as e:
            self.log.error(f"Failed to set up Redis subscriptions: {e}")
    
    async def _handle_notification(self, channel: str, message: str):
        """Handle general notification messages."""
        self.log.info(f"Received notification on {channel}: {message}")
        
        # You can process the message here
        # For example, store it in Redis with a timestamp
        try:
            notification_key = f"notification:{asyncio.get_event_loop().time()}"
            await self.redis_proxy.set(notification_key, message, ex=3600)  # Expire in 1 hour
        except Exception as e:
            self.log.error(f"Error storing notification: {e}")
    
    async def _handle_command(self, channel: str, message: str):
        """Handle command messages for this petal."""
        self.log.info(f"Received command on {channel}: {message}")
        
        try:
            # Try to parse as JSON
            command_data = json.loads(message)
            command_type = command_data.get("type")
            
            if command_type == "ping":
                # Respond to ping commands
                response = {"type": "pong", "timestamp": asyncio.get_event_loop().time()}
                await self.redis_proxy.publish("redis_example_responses", json.dumps(response))
                
            elif command_type == "store":
                # Store data in Redis
                key = command_data.get("key")
                value = command_data.get("value")
                if key and value:
                    await self.redis_proxy.set(f"example:{key}", str(value))
                    
        except json.JSONDecodeError:
            self.log.warning(f"Received non-JSON command: {message}")
        except Exception as e:
            self.log.error(f"Error handling command: {e}")
    
    @http_endpoint(path="/set", method="POST")
    async def set_value(self, request: Request) -> JSONResponse:
        """
        HTTP endpoint to set a key-value pair in Redis.
        
        Example usage:
        POST /petals/redis_example/set
        {
            "key": "my_key",
            "value": "my_value",
            "expire": 3600
        }
        """
        try:
            data = await request.json()
            key = data.get("key")
            value = data.get("value")
            expire = data.get("expire")
            
            if not key or value is None:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Both 'key' and 'value' are required"}
                )
            
            # Store in Redis
            success = await self.redis_proxy.set(f"petal:{key}", str(value), ex=expire)
            
            if success:
                return JSONResponse(content={"status": "success", "key": key})
            else:
                return JSONResponse(
                    status_code=500,
                    content={"error": "Failed to store value in Redis"}
                )
                
        except Exception as e:
            self.log.error(f"Error in set_value endpoint: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @http_endpoint(path="/get/{key}", method="GET")
    async def get_value(self, key: str) -> JSONResponse:
        """
        HTTP endpoint to get a value from Redis.
        
        Example usage:
        GET /petals/redis_example/get/my_key
        """
        try:
            value = await self.redis_proxy.get(f"petal:{key}")
            
            if value is not None:
                return JSONResponse(content={"key": key, "value": value})
            else:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Key not found"}
                )
                
        except Exception as e:
            self.log.error(f"Error in get_value endpoint: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @http_endpoint(path="/publish", method="POST")
    async def publish_message(self, request: Request) -> JSONResponse:
        """
        HTTP endpoint to publish a message to a Redis channel.
        
        Example usage:
        POST /petals/redis_example/publish
        {
            "channel": "notifications",
            "message": "Hello, world!"
        }
        """
        try:
            data = await request.json()
            channel = data.get("channel")
            message = data.get("message")
            
            if not channel or not message:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Both 'channel' and 'message' are required"}
                )
            
            # Publish to Redis
            subscriber_count = await self.redis_proxy.publish(channel, str(message))
            
            return JSONResponse(content={
                "status": "published",
                "channel": channel,
                "subscriber_count": subscriber_count
            })
            
        except Exception as e:
            self.log.error(f"Error in publish_message endpoint: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )
    
    @http_endpoint(path="/status", method="GET")
    async def get_status(self) -> JSONResponse:
        """
        Get the status of the Redis connection and some basic info.
        
        Example usage:
        GET /petals/redis_example/status
        """
        try:
            # Test if Redis is connected by trying to set/get a test key
            test_key = "petal:health_check"
            test_value = "ok"
            
            set_success = await self.redis_proxy.set(test_key, test_value, ex=10)
            if set_success:
                get_value = await self.redis_proxy.get(test_key)
                redis_ok = (get_value == test_value)
                await self.redis_proxy.delete(test_key)  # Clean up
            else:
                redis_ok = False
            
            return JSONResponse(content={
                "petal": self.name,
                "version": self.version,
                "redis_connected": redis_ok,
                "redis_config": {
                    "host": getattr(self.redis_proxy, 'host', None),
                    "port": getattr(self.redis_proxy, 'port', None),
                    "unix_socket": getattr(self.redis_proxy, 'unix_socket_path', None),
                    "db": getattr(self.redis_proxy, 'db', None)
                }
            })
            
        except Exception as e:
            self.log.error(f"Error in get_status endpoint: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": str(e)}
            )


# Entry point for the petal plugin system
def create_petal():
    return ExampleRedisPetal()
