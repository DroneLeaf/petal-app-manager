"""
RedisProxy
==========

Simple Redis proxy for basic pub/sub messaging and key-value operations.
Supports Unix socket connections.
"""

from __future__ import annotations
from typing import List, Optional, Callable, Awaitable
import asyncio
import concurrent.futures
import logging

import redis

from .base import BaseProxy


def setup_file_only_logger(name: str, log_file: str, level: str = "INFO") -> logging.Logger:
    """Setup a logger that only writes to files, not console."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear any existing handlers to avoid console output
    logger.handlers.clear()
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, level.upper()))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s — %(name)s — %(levelname)s — %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(file_handler)
    
    # Prevent propagation to root logger (which might log to console)
    logger.propagate = False
    
    return logger


class RedisProxy(BaseProxy):
    """
    Simple Redis proxy for pub/sub messaging and key-value operations.
    Supports Unix socket connections.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        debug: bool = False,
        unix_socket_path: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.debug = debug
        self.unix_socket_path = unix_socket_path
        
        self._client = None
        self._pubsub_client = None
        self._pubsub = None
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        
        # Set up file-only logging
        self.log = setup_file_only_logger("RedisProxy", "app-redisproxy.log", "INFO")
        
        # Store active subscriptions
        self._subscriptions = {}
        self._subscription_task = None
        
    async def start(self):
        """Initialize the connection to Redis."""
        self._loop = asyncio.get_running_loop()
        
        try:
            # Create Redis client - prioritize Unix socket
            if self.unix_socket_path:
                self.log.info("Initializing Redis connection via Unix socket: %s", self.unix_socket_path)
                self._client = await self._loop.run_in_executor(
                    self._exe,
                    lambda: redis.Redis(
                        unix_socket_path=self.unix_socket_path,
                        db=self.db,
                        password=self.password,
                        decode_responses=True
                    )
                )
                
                # Create separate client for pub/sub operations
                self._pubsub_client = await self._loop.run_in_executor(
                    self._exe,
                    lambda: redis.Redis(
                        unix_socket_path=self.unix_socket_path,
                        db=self.db,
                        password=self.password,
                        decode_responses=True
                    )
                )
            else:
                self.log.info("Initializing Redis connection to %s:%s db=%s", self.host, self.port, self.db)
                self._client = await self._loop.run_in_executor(
                    self._exe,
                    lambda: redis.Redis(
                        host=self.host,
                        port=self.port,
                        db=self.db,
                        password=self.password,
                        decode_responses=True
                    )
                )
                
                # Create separate client for pub/sub operations
                self._pubsub_client = await self._loop.run_in_executor(
                    self._exe,
                    lambda: redis.Redis(
                        host=self.host,
                        port=self.port,
                        db=self.db,
                        password=self.password,
                        decode_responses=True
                    )
                )
        except Exception as e:
            self.log.error(f"Failed to create Redis clients: {e}")
            return
        
        # Test connection
        try:
            ping_result = await self._loop.run_in_executor(self._exe, self._client.ping)
            if ping_result:
                self.log.info("Redis connection established successfully")
                # Initialize pub/sub
                self._pubsub = self._pubsub_client.pubsub()
            else:
                self.log.warning("Redis ping returned unexpected result")
        except Exception as e:
            self.log.error(f"Failed to connect to Redis: {e}")
            
    async def stop(self):
        """Close the Redis connection and clean up resources."""
        # Stop subscription task
        if self._subscription_task and not self._subscription_task.done():
            self._subscription_task.cancel()
            try:
                await self._subscription_task
            except asyncio.CancelledError:
                pass
        
        # Close pub/sub
        if self._pubsub:
            try:
                await self._loop.run_in_executor(self._exe, self._pubsub.close)
            except Exception as e:
                self.log.error(f"Error closing Redis pub/sub: {e}")
        
        # Close Redis connections
        if self._client:
            try:
                await self._loop.run_in_executor(self._exe, self._client.close)
            except Exception as e:
                self.log.error(f"Error closing Redis connection: {e}")
        
        if self._pubsub_client:
            try:
                await self._loop.run_in_executor(self._exe, self._pubsub_client.close)
            except Exception as e:
                self.log.error(f"Error closing Redis pub/sub connection: {e}")
        
        # Shutdown the executor
        if self._exe:
            self._exe.shutdown(wait=True)
            
        self.log.info("RedisProxy stopped")
        
    # ------ Key-Value Operations ------ #
    
    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return None
            
        try:
            result = await self._loop.run_in_executor(
                self._exe, 
                lambda: self._client.get(key)
            )
            # 📥 Log key reads
            self.log.debug(f"📥 Redis GET: {key} = {result}")
            return result
        except Exception as e:
            self.log.error(f"Error getting key {key}: {e}")
            return None
    
    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a value in Redis."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return False
            
        try:
            result = await self._loop.run_in_executor(
                self._exe, 
                lambda: bool(self._client.set(key, value, ex=ex))
            )
            # 📤 Log key writes
            self.log.info(f"📤 Redis SET: {key} = {value} (ex={ex}) -> {result}")
            return result
        except Exception as e:
            self.log.error(f"Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> int:
        """Delete a key from Redis."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        try:
            return await self._loop.run_in_executor(
                self._exe, 
                lambda: self._client.delete(key)
            )
        except Exception as e:
            self.log.error(f"Error deleting key {key}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return False
            
        try:
            result = await self._loop.run_in_executor(
                self._exe, 
                lambda: self._client.exists(key)
            )
            return bool(result)
        except Exception as e:
            self.log.error(f"Error checking existence of key {key}: {e}")
            return False
    
    # ------ Pub/Sub Operations ------ #
    
    def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        try:
            # return self._loop.run_in_executor(
            #     self._exe, 
            #     lambda: self._client.publish(channel, message)
            # )
            self.log.info(f"📤 Redis TX: {channel} - {message}")
            self._client.publish(channel, message)
        except Exception as e:
            self.log.error(f"Error publishing to channel {channel}: {e}")
            return 0
    
    def subscribe(self, channel: str, callback: Callable[[str, str], Awaitable[None]]):
        """Subscribe to a channel with a callback function."""
        if not self._pubsub:
            self.log.error("Redis pub/sub not initialized")
            return
        
        # Store the callback
        self._subscriptions[channel] = callback
        
        # Subscribe to the channel
        try:
            # await self._loop.run_in_executor(
            #     self._exe,
            #     lambda: self._pubsub.subscribe(channel)
            # )
            self._pubsub.subscribe(channel)
            
            # 📥 Log subscription with callback info
            callback_name = getattr(callback, '__name__', str(callback))
            self.log.info(f"📥 Redis SUBSCRIBE: {channel} -> {callback_name}")

            # Start listening if not already started
            if not self._subscription_task:
                self._loop.run_in_executor(
                    self._exe,
                    self._listen_for_messages
                )
                
            self.log.info(f"Subscribed to channel: {channel}")
        except Exception as e:
            self.log.error(f"Error subscribing to channel {channel}: {e}")
    
    def unsubscribe(self, channel: str):
        """Unsubscribe from a channel."""
        if not self._pubsub:
            self.log.error("Redis pub/sub not initialized")
            return
        
        try:
            self._pubsub.unsubscribe(channel)
            # Remove callback
            if channel in self._subscriptions:
                del self._subscriptions[channel]
                
            self.log.info(f"Unsubscribed from channel: {channel}")
        except Exception as e:
            self.log.error(f"Error unsubscribing from channel {channel}: {e}")
    
    def _listen_for_messages(self):
        """Listen for messages from subscribed channels."""
        while True:
            try:

                message = self._pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'message':
                    channel = message['channel']
                    data = message['data']
                    self.log.info(f"Received at channel: {channel}, with data: {data}")
                    
                    # Call the registered callback
                    if channel in self._subscriptions:
                        callback = self._subscriptions[channel]
                        try:
                            callback(channel, data)
                            self.log.info(f"Callback executed for channel: {channel}")  
                        except Exception as e:
                            self.log.error(f"Error in callback for channel {channel}: {e}")
                            
            except Exception as e:
                if "timeout" not in str(e).lower():
                    self.log.error(f"Error listening for messages: {e}")
                
