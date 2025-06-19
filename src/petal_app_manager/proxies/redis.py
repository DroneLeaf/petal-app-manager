"""
RedisProxy
==========

• Provides access to Redis key-value store
• Handles connection management and error recovery
• Abstracts async/sync conversion for Redis operations
• Provides methods for common Redis operations like get, set, delete

This proxy allows petals to interact with Redis without worrying about
connection management or blocking operations.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Union
import asyncio
import concurrent.futures
import logging

import redis

from .base import BaseProxy

class RedisProxy(BaseProxy):
    """
    Proxy for communicating with a Redis server.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        debug: bool = False,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.debug = debug
        
        self._client = None
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.log = logging.getLogger("RedisProxy")
        
    async def start(self):
        """Initialize the connection to Redis."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing Redis connection to %s:%s db=%s", self.host, self.port, self.db)
        
        # Create Redis client in executor to avoid blocking
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
        
        # Test connection
        try:
            ping_result = await self._loop.run_in_executor(self._exe, self._client.ping)
            if ping_result:
                self.log.info("Redis connection established successfully")
            else:
                self.log.warning("Redis ping returned unexpected result")
        except Exception as e:
            self.log.error(f"Failed to connect to Redis: {e}")
            
    async def stop(self):
        """Close the Redis connection and clean up resources."""
        if self._client:
            try:
                # First close the Redis connection
                await self._loop.run_in_executor(self._exe, self._client.close)
            except Exception as e:
                self.log.error(f"Error closing Redis connection: {e}")
        
        # Then shutdown the executor with wait=True to ensure all tasks complete
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