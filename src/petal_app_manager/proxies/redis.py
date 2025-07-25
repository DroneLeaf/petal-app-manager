"""
RedisProxy
==========

• Provides access to Redis key-value store
• Handles connection management and error recovery
• Abstracts async/sync conversion for Redis operations
• Provides methods for common Redis operations like get, set, delete
• Supports two-way communication with external applications via pub/sub and message queues

This proxy allows petals to interact with Redis without worrying about
connection management or blocking operations.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Union, Callable, Awaitable
import asyncio
import concurrent.futures
import logging
import json
import time
import uuid
from enum import Enum
from dataclasses import dataclass, asdict

import redis

from .base import BaseProxy

class MessagePriority(Enum):
    """Message priority levels for queue processing."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class MessageStatus(Enum):
    """Message status for tracking."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

@dataclass
class CommunicationMessage:
    """Structure for communication messages between applications."""
    id: str
    sender: str
    recipient: str
    message_type: str
    payload: Dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = None
    reply_to: Optional[str] = None
    timeout: Optional[int] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['priority'] = self.priority.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommunicationMessage':
        """Create instance from dictionary."""
        data['priority'] = MessagePriority(data['priority'])
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_json(cls, json_str: str) -> 'CommunicationMessage':
        """Create instance from JSON string."""
        return cls.from_dict(json.loads(json_str))

class RedisProxy(BaseProxy):
    """
    Proxy for communicating with a Redis server with two-way communication support.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        debug: bool = False,
        unix_socket_path: Optional[str] = None,
        app_id: str = "petal-app-manager",
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.debug = debug
        self.unix_socket_path = unix_socket_path
        self.app_id = app_id
        
        self._client = None
        self._pubsub_client = None
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.log = logging.getLogger("RedisProxy")
        
        # Communication state
        self._message_handlers: Dict[str, Callable[[CommunicationMessage], Awaitable[Optional[CommunicationMessage]]]] = {}
        self._subscription_tasks: List[asyncio.Task] = []
        self._pending_replies: Dict[str, asyncio.Future] = {}
        self._is_listening = False
        
        # Queue and channel naming conventions
        self._inbox_queue = f"queue:{self.app_id}:inbox"
        self._outbox_queue = f"queue:{self.app_id}:outbox"
        self._status_hash = f"status:{self.app_id}"
        self._pub_channel = f"channel:{self.app_id}"
        self._sub_channel = f"channel:broadcast"
        
    async def start(self):
        """Initialize the connection to Redis and start communication services."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing Redis connection to %s:%s db=%s", self.host, self.port, self.db)
        
        # Create Redis clients in executor to avoid blocking
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
                decode_responses=True,
                unix_socket_path=self.unix_socket_path if self.unix_socket_path else None
            )
        )
        
        # Test connection
        try:
            ping_result = await self._loop.run_in_executor(self._exe, self._client.ping)
            if ping_result:
                self.log.info("Redis connection established successfully")
                # Initialize communication infrastructure
                await self._initialize_communication()
            else:
                self.log.warning("Redis ping returned unexpected result")
        except Exception as e:
            self.log.error(f"Failed to connect to Redis: {e}")
            
    async def stop(self):
        """Close the Redis connection and clean up resources."""
        # Stop listening first
        if self._is_listening:
            await self.stop_listening()
        
        # Cancel subscription tasks
        for task in self._subscription_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._subscription_tasks:
            try:
                await asyncio.gather(*self._subscription_tasks, return_exceptions=True)
            except Exception as e:
                self.log.error(f"Error waiting for subscription tasks: {e}")
        
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
        
        # Shutdown the executor with wait=True to ensure all tasks complete
        if self._exe:
            self._exe.shutdown(wait=True)
            
        self.log.info("RedisProxy stopped")
        
    # ------ Public API methods ------ #
    
    async def get(self, key: str) -> Optional[str]:
        """
        Get a value from Redis.
        
        Args:
            key: The key to retrieve
            
        Returns:
            The value as a string, or None if the key doesn't exist
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return None
            
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.get(key)
        )
    
    async def set(
        self, 
        key: str, 
        value: str, 
        ex: Optional[int] = None
    ) -> bool:
        """
        Set a value in Redis.
        
        Args:
            key: The key to set
            value: The value to set
            ex: Optional expiration time in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return False
            
        try:
            return await self._loop.run_in_executor(
                self._exe, 
                lambda: bool(self._client.set(key, value, ex=ex))
            )
        except Exception as e:
            self.log.error(f"Error setting key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> int:
        """
        Delete a key from Redis.
        
        Args:
            key: The key to delete
            
        Returns:
            Number of keys deleted (0 or 1)
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.delete(key)
        )
    
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in Redis.
        
        Args:
            key: The key to check
            
        Returns:
            True if the key exists, False otherwise
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return False
            
        result = await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.exists(key)
        )
        return bool(result)
    
    async def keys(self, pattern: str = "*") -> List[str]:
        """
        Get all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (default "*" matches all keys)
            
        Returns:
            List of matching keys
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return []
            
        keys = await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.keys(pattern)
        )
        return keys
    
    async def flushdb(self) -> bool:
        """
        Delete all keys in the current database.
        
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return False
            
        try:
            return await self._loop.run_in_executor(
                self._exe, 
                self._client.flushdb
            )
        except Exception as e:
            self.log.error(f"Error flushing database: {e}")
            return False
    
    async def publish(self, channel: str, message: str) -> int:
        """
        Publish a message to a channel.
        
        Args:
            channel: The channel to publish to
            message: The message to publish
            
        Returns:
            Number of clients that received the message
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.publish(channel, message)
        )
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        """
        Get a value from a hash.
        
        Args:
            name: The hash name
            key: The key within the hash
            
        Returns:
            The value, or None if it doesn't exist
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return None
            
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.hget(name, key)
        )
    
    async def hset(self, name: str, key: str, value: str) -> int:
        """
        Set a value in a hash.
        
        Args:
            name: The hash name
            key: The key within the hash
            value: The value to set
            
        Returns:
            1 if a new field was created, 0 if an existing field was updated
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return 0
            
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._client.hset(name, key, value)
        )
    
    async def subscribe(
        self, 
        channel: str, 
        callback: Callable[[str, str], Awaitable[None]]
    ):
        """
        Subscribe to a Redis channel.
        
        Args:
            channel: The channel to subscribe to
            callback: The callback function to handle messages
            
        Returns:
            None
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return
            
        pubsub = self._client.pubsub()
        await self._loop.run_in_executor(
            self._exe, 
            pubsub.subscribe, 
            channel
        )
        
        self.log.info(f"Subscribed to channel: {channel}")
        
        async def run():
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        await callback(message["channel"], message["data"])
            except Exception as e:
                self.log.error(f"Error in subscription listener: {e}")
        
        # Run the listener in the executor
        await self._loop.run_in_executor(self._exe, run)
    
    async def unsubscribe(self, channel: str):
        """
        Unsubscribe from a Redis channel.
        
        Args:
            channel: The channel to unsubscribe from
            
        Returns:
            None
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return
            
        pubsub = self._client.pubsub()
        await self._loop.run_in_executor(
            self._exe, 
            pubsub.unsubscribe, 
            channel
        )
        
        self.log.info(f"Unsubscribed from channel: {channel}")
    
    # ------ Two-Way Communication Methods ------ #
    
    async def _initialize_communication(self):
        """Initialize communication infrastructure."""
        try:
            # Set application status as online
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hset(self._status_hash, "status", "online")
            )
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hset(self._status_hash, "last_seen", str(time.time()))
            )
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hset(self._status_hash, "app_id", self.app_id)
            )
            
            self.log.info("Communication infrastructure initialized")
        except Exception as e:
            self.log.error(f"Failed to initialize communication: {e}")
    
    async def register_message_handler(
        self, 
        message_type: str, 
        handler: Callable[[CommunicationMessage], Awaitable[Optional[CommunicationMessage]]]
    ):
        """
        Register a handler for specific message types.
        
        Args:
            message_type: Type of message to handle
            handler: Async function that processes the message and optionally returns a response
        """
        self._message_handlers[message_type] = handler
        self.log.info(f"Registered handler for message type: {message_type}")
    
    async def unregister_message_handler(self, message_type: str):
        """Unregister a message handler."""
        if message_type in self._message_handlers:
            del self._message_handlers[message_type]
            self.log.info(f"Unregistered handler for message type: {message_type}")
    
    async def send_message(
        self,
        recipient: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        timeout: Optional[int] = None,
        wait_for_reply: bool = False
    ) -> Optional[CommunicationMessage]:
        """
        Send a message to another application.
        
        Args:
            recipient: ID of the receiving application
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            timeout: Message timeout in seconds
            wait_for_reply: Whether to wait for a reply
            
        Returns:
            Reply message if wait_for_reply=True, None otherwise
        """
        if not self._client:
            self.log.error("Redis client not initialized")
            return None
        
        message_id = str(uuid.uuid4())
        message = CommunicationMessage(
            id=message_id,
            sender=self.app_id,
            recipient=recipient,
            message_type=message_type,
            payload=payload,
            priority=priority,
            timeout=timeout
        )
        
        try:
            # Add to recipient's inbox queue with priority
            queue_name = f"queue:{recipient}:inbox"
            priority_score = priority.value * 1000 + time.time()
            
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.zadd(queue_name, {message.to_json(): priority_score})
            )
            
            # Publish notification
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.publish(f"channel:{recipient}", f"new_message:{message_id}")
            )
            
            # Store message metadata
            metadata_key = f"message:{message_id}"
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hset(metadata_key, mapping={
                    "status": MessageStatus.PENDING.value,
                    "sender": self.app_id,
                    "recipient": recipient,
                    "timestamp": str(time.time()),
                    "type": message_type
                })
            )
            
            # Set TTL for message metadata
            if timeout:
                await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._client.expire(metadata_key, timeout)
                )
            
            self.log.debug(f"Sent message {message_id} to {recipient}")
            
            # Wait for reply if requested
            if wait_for_reply:
                return await self._wait_for_reply(message_id, timeout or 30)
            
            return None
            
        except Exception as e:
            self.log.error(f"Failed to send message: {e}")
            return None
    
    async def _wait_for_reply(self, message_id: str, timeout: int) -> Optional[CommunicationMessage]:
        """Wait for a reply to a specific message."""
        future = asyncio.Future()
        self._pending_replies[message_id] = future
        
        try:
            reply = await asyncio.wait_for(future, timeout=timeout)
            return reply
        except asyncio.TimeoutError:
            self.log.warning(f"Timeout waiting for reply to message {message_id}")
            return None
        finally:
            self._pending_replies.pop(message_id, None)
    
    async def send_reply(
        self,
        original_message: CommunicationMessage,
        payload: Dict[str, Any]
    ) -> bool:
        """
        Send a reply to a received message.
        
        Args:
            original_message: The original message being replied to
            payload: Reply payload
            
        Returns:
            True if reply was sent successfully
        """
        return await self.send_message(
            recipient=original_message.sender,
            message_type=f"{original_message.message_type}_reply",
            payload=payload,
            priority=original_message.priority
        ) is not None
    
    async def start_listening(self):
        """Start listening for incoming messages."""
        if self._is_listening:
            self.log.warning("Already listening for messages")
            return
        
        self._is_listening = True
        
        # Start queue processing task
        queue_task = asyncio.create_task(self._process_inbox_queue())
        self._subscription_tasks.append(queue_task)
        
        # Start pub/sub listening task
        pubsub_task = asyncio.create_task(self._listen_pubsub())
        self._subscription_tasks.append(pubsub_task)
        
        self.log.info("Started listening for messages")
    
    async def stop_listening(self):
        """Stop listening for incoming messages."""
        self._is_listening = False
        
        # Update status
        if self._client:
            try:
                await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._client.hset(self._status_hash, "status", "offline")
                )
            except Exception as e:
                self.log.error(f"Error updating status: {e}")
        
        self.log.info("Stopped listening for messages")
    
    async def _process_inbox_queue(self):
        """Process messages from the inbox queue."""
        while self._is_listening:
            try:
                # Get highest priority message
                result = await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._client.zpopmax(self._inbox_queue, 1)
                )
                
                if result:
                    message_json, _ = result[0]
                    try:
                        message = CommunicationMessage.from_json(message_json)
                        await self._handle_received_message(message)
                    except json.JSONDecodeError as e:
                        self.log.error(f"Failed to decode message: {e}")
                else:
                    # No messages, wait a bit
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                self.log.error(f"Error processing inbox queue: {e}")
                await asyncio.sleep(1)
    
    async def _listen_pubsub(self):
        """Listen for pub/sub notifications."""
        try:
            pubsub = self._pubsub_client.pubsub()
            await self._loop.run_in_executor(
                self._exe,
                lambda: pubsub.subscribe(self._pub_channel, self._sub_channel)
            )
            
            while self._is_listening:
                message = await self._loop.run_in_executor(
                    self._exe,
                    lambda: pubsub.get_message(timeout=1)
                )
                
                if message and message['type'] == 'message':
                    await self._handle_pubsub_message(message['data'])
                    
        except Exception as e:
            self.log.error(f"Error in pub/sub listener: {e}")
        finally:
            try:
                await self._loop.run_in_executor(self._exe, pubsub.close)
            except:
                pass
    
    async def _handle_pubsub_message(self, data: str):
        """Handle pub/sub notification messages."""
        try:
            if data.startswith("new_message:"):
                # Force check of inbox queue
                self.log.debug("Received new message notification")
        except Exception as e:
            self.log.error(f"Error handling pub/sub message: {e}")
    
    async def _handle_received_message(self, message: CommunicationMessage):
        """Process a received message."""
        try:
            # Update message status
            metadata_key = f"message:{message.id}"
            await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hset(metadata_key, "status", MessageStatus.PROCESSING.value)
            )
            
            # Check if this is a reply
            if message.reply_to and message.reply_to in self._pending_replies:
                future = self._pending_replies[message.reply_to]
                if not future.done():
                    future.set_result(message)
                return
            
            # Find handler for message type
            handler = self._message_handlers.get(message.message_type)
            if handler:
                try:
                    reply = await handler(message)
                    
                    # Send reply if handler returned one
                    if reply:
                        await self.send_reply(message, reply.payload)
                    
                    # Mark as completed
                    await self._loop.run_in_executor(
                        self._exe,
                        lambda: self._client.hset(metadata_key, "status", MessageStatus.COMPLETED.value)
                    )
                    
                except Exception as e:
                    self.log.error(f"Error in message handler: {e}")
                    await self._loop.run_in_executor(
                        self._exe,
                        lambda: self._client.hset(metadata_key, "status", MessageStatus.FAILED.value)
                    )
            else:
                self.log.warning(f"No handler registered for message type: {message.message_type}")
                
        except Exception as e:
            self.log.error(f"Error handling received message: {e}")
    
    async def get_application_status(self, app_id: str) -> Optional[Dict[str, str]]:
        """
        Get the status of another application.
        
        Args:
            app_id: ID of the application to check
            
        Returns:
            Status information or None if not found
        """
        if not self._client:
            return None
        
        try:
            status = await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hgetall(f"status:{app_id}")
            )
            return status if status else None
        except Exception as e:
            self.log.error(f"Error getting application status: {e}")
            return None
    
    async def list_online_applications(self) -> List[str]:
        """Get list of online applications."""
        if not self._client:
            return []
        
        try:
            # Find all status keys
            status_keys = await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.keys("status:*")
            )
            
            online_apps = []
            for key in status_keys:
                status = await self._loop.run_in_executor(
                    self._exe,
                    lambda: self._client.hget(key, "status")
                )
                if status == "online":
                    app_id = key.split(":", 1)[1]
                    online_apps.append(app_id)
            
            return online_apps
        except Exception as e:
            self.log.error(f"Error listing online applications: {e}")
            return []
    
    async def get_message_status(self, message_id: str) -> Optional[str]:
        """Get the status of a sent message."""
        if not self._client:
            return None
        
        try:
            status = await self._loop.run_in_executor(
                self._exe,
                lambda: self._client.hget(f"message:{message_id}", "status")
            )
            return status
        except Exception as e:
            self.log.error(f"Error getting message status: {e}")
            return None