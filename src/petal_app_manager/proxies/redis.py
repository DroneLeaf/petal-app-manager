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
import time

from .base import BaseProxy


class RedisProxy(BaseProxy):
    """
    Simple Redis proxy for pub/sub messaging and key-value operations.
    Supports Unix socket connections.
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
        self._pubsub_pattern = None
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.log = logging.getLogger("RedisProxy")
        
        # Communication and health check attributes
        self.app_id = f"redis-proxy-{id(self)}"  # Unique app identifier
        self._is_listening = False  # Whether actively listening for messages
        self._message_handlers = {}  # Active message handlers
        self._subscription_tasks = {}  # Active subscription tasks
        
        # Store active subscriptions
        self._subscriptions = {}  # normal channel subscriptions
        self._subscription_task = None
        # Pattern subscription state
        self._pattern_callbacks = {}  # channel: callback for pattern subpub
        self._pattern_subscription_task = None
        self._current_pattern = None
        
        # Shutdown flag to control infinite loops
        self._shutdown_flag = False
        
    async def start(self):
        """Initialize the connection to Redis."""
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
                # Initialize pattern pub/sub (separate client for patterns)
                self._pubsub_pattern = self._pubsub_client.pubsub()
                self._subscribe_pattern("/petal-*")  # Default pattern
                
                # Set listening state to True after successful connection and pub/sub setup
                self._is_listening = True
                self.log.info(f"RedisProxy {self.app_id} is now listening for messages")
            else:
                self.log.warning("Redis ping returned unexpected result")
        except Exception as e:
            self.log.error(f"Failed to connect to Redis: {e}")
            
    async def stop(self):
        """Close the Redis connection and clean up resources."""
        self.log.info("Stopping RedisProxy...")
        
        # Set shutdown flag to stop infinite loops
        self._shutdown_flag = True
        # Stop listening state
        self._is_listening = False
        
        # Stop subscription tasks
        if self._subscription_task and not self._subscription_task.done():
            self._subscription_task.cancel()
            try:
                await self._subscription_task
            except asyncio.CancelledError:
                pass
                
        if self._pattern_subscription_task and not self._pattern_subscription_task.done():
            self._pattern_subscription_task.cancel()
            try:
                await self._pattern_subscription_task
            except asyncio.CancelledError:
                pass
        
        # Clear handlers and tasks
        self._message_handlers.clear()
        self._subscription_tasks.clear()
        
        # Close pub/sub
        if self._pubsub:
            try:
                await self._loop.run_in_executor(self._exe, self._pubsub.close)
            except Exception as e:
                self.log.error(f"Error closing Redis pub/sub: {e}")
                
        if self._pubsub_pattern:
            try:
                await self._loop.run_in_executor(self._exe, self._pubsub_pattern.close)
            except Exception as e:
                self.log.error(f"Error closing Redis pattern pub/sub: {e}")
        
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
        
        # Shutdown the executor with a timeout
        if self._exe:
            self._exe.shutdown(wait=False)  # Don't wait for infinite loops
            
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
    
    async def list_online_applications(self) -> List[str]:
        """List online applications by checking Redis keys for app registrations."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return []
            
        try:
            # Look for keys that match application registration pattern
            # This is a simple implementation - can be customized based on your app registration pattern
            result = await self._loop.run_in_executor(
                self._exe, 
                lambda: self._client.keys("app:*:online")
            )
            # Extract app names from keys like "app:myapp:online"
            apps = [key.split(':')[1] for key in result if ':' in key and len(key.split(':')) >= 3]
            return apps
        except Exception as e:
            self.log.error(f"Error listing online applications: {e}")
            return []
    
    # ------ Pub/Sub Operations ------ #
    
    def publish(self, channel: str, message: str) -> int:
        """Publish a message to a channel."""
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        try:
            result = self._client.publish(channel, message)
            return result
        except Exception as e:
            self.log.error(f"Error publishing to channel {channel}: {e}")
            return 0
    
    def subscribe(self, channel: str, callback: Callable[[str, str], Awaitable[None]]):
        """Subscribe to a channel with a callback function."""
        if not self._pubsub:
            self.log.error("Redis pub/sub not initialized")
            return
        
        # Store the callback in both tracking dictionaries
        self._subscriptions[channel] = callback
        self._message_handlers[channel] = callback
        
        # Subscribe to the channel
        try:
            # await self._loop.run_in_executor(
            #     self._exe,
            #     lambda: self._pubsub.subscribe(channel)
            # )
            self._pubsub.subscribe(channel)
            # Start listening if not already started
            if not self._subscription_task and self._loop:
                self._subscription_task = self._loop.create_task(self._listen_for_messages())
                # Track this task
                self._subscription_tasks[channel] = self._subscription_task
                
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
            # Remove callback from both tracking dictionaries
            if channel in self._subscriptions:
                del self._subscriptions[channel]
            if channel in self._message_handlers:
                del self._message_handlers[channel]
            if channel in self._subscription_tasks:
                del self._subscription_tasks[channel]
                
            self.log.info(f"Unsubscribed from channel: {channel}")
        except Exception as e:
            self.log.error(f"Error unsubscribing from channel {channel}: {e}")
    
    def _subscribe_pattern(self, pattern: str = "/petal-*"):
        """Subscribe to channels matching a pattern. Only one pattern at a time."""
        if not self._pubsub_pattern:
            self.log.error("Redis pattern pub/sub not initialized")
            return
        # Only support one pattern at a time
        if self._current_pattern and self._current_pattern != pattern:
            self.log.warning(f"Switching from pattern '{self._current_pattern}' to '{pattern}'")
            self._unsubscribe_pattern(self._current_pattern)
        self._current_pattern = pattern
        try:
            self._pubsub_pattern.psubscribe(pattern)
            # Start listening if not already started
            if not self._pattern_subscription_task and self._loop:
                self._pattern_subscription_task = self._loop.create_task(self._listen_for_pattern_messages())
            self.log.info(f"Subscribed to pattern: {pattern}")
        except Exception as e:
            self.log.error(f"Error subscribing to pattern {pattern}: {e}")

    def register_pattern_channel_callback(self, channel: str, callback: Callable[[str, str], Awaitable[None]]):
        """Register a callback for a specific channel for pattern subscriptions."""
        self._pattern_callbacks[channel] = callback
        self.log.info(f"Registered pattern callback for channel: {channel}")

    def unregister_pattern_channel_callback(self, channel: str):
        """Unregister a callback for a specific channel for pattern subscriptions."""
        if channel in self._pattern_callbacks:
            del self._pattern_callbacks[channel]
            self.log.info(f"Unregistered pattern callback for channel: {channel}")
        else:
            self.log.warning(f"No pattern callback registered for channel: {channel}")

    def _unsubscribe_pattern(self, pattern: str = None):
        """Unsubscribe from the current pattern."""
        if not self._pubsub_pattern:
            self.log.error("Redis pattern pub/sub not initialized")
            return
        # Use current pattern if none specified
        if pattern is None:
            pattern = self._current_pattern
        if not pattern:
            self.log.warning("No pattern to unsubscribe from")
            return
        try:
            self._pubsub_pattern.punsubscribe(pattern)
            if pattern == self._current_pattern:
                self._current_pattern = None
            self._pattern_callbacks.clear()
            self.log.info(f"Unsubscribed from pattern: {pattern}")
        except Exception as e:
            self.log.error(f"Error unsubscribing from pattern {pattern}: {e}")
    
    async def _listen_for_pattern_messages(self):
        """Listen for messages from pattern subscriptions."""
        while not self._shutdown_flag:
            try:
                message = await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._pubsub_pattern.get_message(timeout=1.0)
                )
                if message and message['type'] == 'pmessage':
                    channel = message['channel']
                    pattern = message['pattern']
                    data = message['data']
                    self.log.info(f"Received pattern message at channel: {channel} (pattern: {pattern}) with data: {data}")
                    # Check for channel callback in pattern_callbacks
                    if channel in self._pattern_callbacks:
                        callback = self._pattern_callbacks[channel]
                        try:
                            callback(channel, data)
                            self.log.info(f"Pattern callback executed for channel: {channel}")
                        except Exception as e:
                            self.log.error(f"Error in pattern callback for channel {channel}: {e}")
            except Exception as e:
                if "timeout" not in str(e).lower() and not self._shutdown_flag:
                    self.log.error(f"Error listening for pattern messages: {e}")
    
    async def _listen_for_messages(self):
        """Listen for PubSub messages and auto-reconnect on errors."""
        while not self._shutdown_flag:
            try:
                message = await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._pubsub.get_message(timeout=1.0)
                )
                # Only care about real published messages
                if message and message.get('type') == 'message':
                    # Decode bytes to str if needed
                    channel = message['channel']
                    if isinstance(channel, bytes):
                        channel = channel.decode('utf-8', 'ignore')
                    data = message['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8', 'ignore')

                    self.log.info(f"Received at channel: {channel}, with data: {data}")

                    # Invoke callback
                    callback = self._subscriptions.get(channel)
                    if callback:
                        try:
                            callback(channel, data)
                            self.log.info(f"Callback executed for channel: {channel}")
                        except Exception as cb_err:
                            self.log.error(f"Error in callback for channel {channel}: {cb_err}")

            except redis.exceptions.ConnectionError as conn_err:
                if not self._shutdown_flag:
                    self.log.error(f"Connection lost: {conn_err!r}; reconnecting in 1s")
                    await asyncio.sleep(1)
                    await self._reconnect_pubsub()

            except (IOError, OSError) as io_err:
                if not self._shutdown_flag:
                    self.log.error(f"I/O error on PubSub socket: {io_err!r}; reconnecting in 1s")
                    await asyncio.sleep(1)
                    await self._reconnect_pubsub()

            except IndexError as idx_err:
                # Defensive: swallow stray indexing bugs and keep going
                self.log.error(f"Unexpected indexing error: {idx_err!r}; continuing")

            except Exception as e:
                # Anything else that isn’t just a timeout
                msg = str(e).lower()
                if "timeout" not in msg:
                    self.log.error(f"Error listening for messages: {e!r}")

    def _reconnect_pubsub(self):
        """Tear down the old PubSub and re-subscribe to all channels."""
        self.log.warning("_reconnect_pubsub method is deprecated - Redis connections should be properly managed")
                
