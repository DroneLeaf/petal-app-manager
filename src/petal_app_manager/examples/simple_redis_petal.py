"""
Simple Redis Petal Example
==========================

Minimal example showing how to use the Redis proxy within petal endpoints.
"""

import asyncio
import json
from fastapi import Request
from fastapi.responses import JSONResponse

from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import http_endpoint


class SimpleRedisPetal(Petal):
    """Minimal Redis petal showing basic usage."""
    
    def __init__(self):
        super().__init__()
        self.name = "simple_redis"
        self.version = "1.0.0"
    
    @http_endpoint(path="/store", method="POST")
    async def store_data(self, request: Request) -> JSONResponse:
        """
        Store data in Redis.
        POST /petals/simple_redis/store
        {
            "key": "my_key",
            "value": "my_value"
        }
        """
        data = await request.json()
        key = data.get("key")
        value = data.get("value")
        
        # Get Redis proxy from injected proxies
        redis = self.proxies["redis"]
        
        # Store the data
        success = await redis.set(f"simple:{key}", str(value))
        
        return JSONResponse({
            "success": success,
            "key": key,
            "stored": success
        })
    
    @http_endpoint(path="/retrieve/{key}", method="GET")
    async def retrieve_data(self, key: str) -> JSONResponse:
        """
        Retrieve data from Redis.
        GET /petals/simple_redis/retrieve/my_key
        """
        # Get Redis proxy
        redis = self.proxies["redis"]
        
        # Get the data
        value = await redis.get(f"simple:{key}")
        
        return JSONResponse({
            "key": key,
            "value": value,
            "found": value is not None
        })
    
    @http_endpoint(path="/broadcast", method="POST")
    async def broadcast_message(self, request: Request) -> JSONResponse:
        """
        Broadcast a message via Redis pub/sub.
        POST /petals/simple_redis/broadcast
        {
            "channel": "notifications",
            "message": "Hello everyone!"
        }
        """
        data = await request.json()
        channel = data.get("channel", "general")
        message = data.get("message")
        
        # Get Redis proxy
        redis = self.proxies["redis"]
        
        # Publish the message
        subscriber_count = await redis.publish(channel, message)
        
        return JSONResponse({
            "channel": channel,
            "message": message,
            "subscribers": subscriber_count
        })
    
    @http_endpoint(path="/subscribe/{channel}", method="POST")
    async def subscribe_to_channel(self, channel: str) -> JSONResponse:
        """
        Subscribe to a Redis channel.
        POST /petals/simple_redis/subscribe/notifications
        """
        # Get Redis proxy
        redis = self.proxies["redis"]
        
        # Define a simple message handler
        async def message_handler(ch: str, msg: str):
            self.log.info(f"Received message on {ch}: {msg}")
            # You could store this in a database, send to webhooks, etc.
        
        try:
            # Subscribe to the channel
            await redis.subscribe(channel, message_handler)
            
            return JSONResponse({
                "success": True,
                "channel": channel,
                "message": f"Subscribed to {channel}"
            })
            
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": str(e)
            }, status_code=500)


# Entry point for the plugin system
def create_petal():
    return SimpleRedisPetal()
