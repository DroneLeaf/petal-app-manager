import pytest
import pytest_asyncio
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock

from typing import Generator, AsyncGenerator

from petal_app_manager.proxies.redis import RedisProxy

@pytest_asyncio.fixture
async def proxy() -> AsyncGenerator[RedisProxy, None]:
    """Create a RedisProxy instance for testing with mocked Redis client."""
    # Create the proxy with test configuration
    proxy = RedisProxy(host="localhost", port=6379, db=0, debug=True)
    
    # Use try/finally to ensure proper cleanup
    try:
        # Mock the actual Redis client creation
        with patch('redis.Redis') as mock_redis:
            # Setup the mock Redis client
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client
            
            # Store reference to the mock for assertions
            proxy._mock_client = mock_client
            
            await proxy.start()
            yield proxy
    finally:
        # Always try to stop the proxy even if tests fail
        try:
            if hasattr(proxy, "_client") and proxy._client:
                await proxy.stop()
        except Exception as e:
            print(f"Error during proxy cleanup: {e}")

@pytest.mark.asyncio
async def test_start_connection(proxy: RedisProxy):
    """Test that Redis connection is established correctly."""
    assert proxy._client is not None
    # The ping should have been called during start
    proxy._mock_client.ping.assert_called_once()

@pytest.mark.asyncio
async def test_stop_connection(proxy: RedisProxy):
    """Test that Redis connection is closed properly."""
    # Replace the close method with a mock, don't use context manager
    original_close = proxy._mock_client.close
    mock_close = MagicMock()
    proxy._mock_client.close = mock_close
    
    try:
        # Call the stop method
        await proxy.stop()
        
        # Verify the mock was called
        mock_close.assert_called_once()
    finally:
        # Restore original method to avoid affecting other tests
        proxy._mock_client.close = original_close

@pytest.mark.asyncio
async def test_get(proxy: RedisProxy):
    """Test retrieving a value from Redis."""
    # Setup mock return value
    proxy._mock_client.get.return_value = "test-value"
    
    # Call the method
    result = await proxy.get("test-key")
    
    # Assert results
    assert result == "test-value"
    proxy._mock_client.get.assert_called_once_with("test-key")

@pytest.mark.asyncio
async def test_get_nonexistent_key(proxy: RedisProxy):
    """Test retrieving a non-existent key."""
    # Setup mock return value for non-existent key
    proxy._mock_client.get.return_value = None
    
    # Call the method
    result = await proxy.get("nonexistent-key")
    
    # Assert results
    assert result is None
    proxy._mock_client.get.assert_called_once_with("nonexistent-key")

@pytest.mark.asyncio
async def test_set(proxy: RedisProxy):
    """Test setting a value in Redis."""
    # Setup mock return value
    proxy._mock_client.set.return_value = True
    
    # Call the method
    result = await proxy.set("test-key", "test-value")
    
    # Assert results
    assert result is True
    proxy._mock_client.set.assert_called_once_with("test-key", "test-value", ex=None)

@pytest.mark.asyncio
async def test_set_with_expiry(proxy: RedisProxy):
    """Test setting a value with expiration time."""
    # Setup mock return value
    proxy._mock_client.set.return_value = True
    
    # Call the method with expiry
    result = await proxy.set("test-key", "test-value", ex=60)
    
    # Assert results
    assert result is True
    proxy._mock_client.set.assert_called_once_with("test-key", "test-value", ex=60)

@pytest.mark.asyncio
async def test_delete(proxy: RedisProxy):
    """Test deleting a key from Redis."""
    # Setup mock return value
    proxy._mock_client.delete.return_value = 1
    
    # Call the method
    result = await proxy.delete("test-key")
    
    # Assert results
    assert result == 1
    proxy._mock_client.delete.assert_called_once_with("test-key")

@pytest.mark.asyncio
async def test_exists(proxy: RedisProxy):
    """Test checking if a key exists in Redis."""
    # Setup mock return value
    proxy._mock_client.exists.return_value = 1
    
    # Call the method
    result = await proxy.exists("test-key")
    
    # Assert results
    assert result is True
    proxy._mock_client.exists.assert_called_once_with("test-key")

@pytest.mark.asyncio
async def test_keys(proxy: RedisProxy):
    """Test getting keys matching a pattern."""
    # Setup mock return value
    proxy._mock_client.keys.return_value = ["key1", "key2", "key3"]
    
    # Call the method
    result = await proxy.keys("key*")
    
    # Assert results
    assert result == ["key1", "key2", "key3"]
    proxy._mock_client.keys.assert_called_once_with("key*")

@pytest.mark.asyncio
async def test_flushdb(proxy: RedisProxy):
    """Test flushing the database."""
    # Setup mock return value
    proxy._mock_client.flushdb.return_value = True
    
    # Call the method
    result = await proxy.flushdb()
    
    # Assert results
    assert result is True
    proxy._mock_client.flushdb.assert_called_once()

@pytest.mark.asyncio
async def test_publish(proxy: RedisProxy):
    """Test publishing a message to a channel."""
    # Setup mock return value
    proxy._mock_client.publish.return_value = 2  # 2 clients received
    
    # Call the method
    result = await proxy.publish("test-channel", "test-message")
    
    # Assert results
    assert result == 2
    proxy._mock_client.publish.assert_called_once_with("test-channel", "test-message")

@pytest.mark.asyncio
async def test_hget(proxy: RedisProxy):
    """Test getting a value from a hash."""
    # Setup mock return value
    proxy._mock_client.hget.return_value = "hash-value"
    
    # Call the method
    result = await proxy.hget("hash-name", "field-key")
    
    # Assert results
    assert result == "hash-value"
    proxy._mock_client.hget.assert_called_once_with("hash-name", "field-key")

@pytest.mark.asyncio
async def test_hset(proxy: RedisProxy):
    """Test setting a value in a hash."""
    # Setup mock return value
    proxy._mock_client.hset.return_value = 1  # New field was created
    
    # Call the method
    result = await proxy.hset("hash-name", "field-key", "field-value")
    
    # Assert results
    assert result == 1
    proxy._mock_client.hset.assert_called_once_with("hash-name", "field-key", "field-value")

@pytest.mark.asyncio
async def test_client_not_initialized():
    """Test behavior when Redis client is not initialized."""
    # Create proxy but don't start it
    proxy = RedisProxy(host="localhost", port=6379)
    
    # Call methods without initializing
    get_result = await proxy.get("key")
    set_result = await proxy.set("key", "value")
    delete_result = await proxy.delete("key")
    exists_result = await proxy.exists("key")
    keys_result = await proxy.keys()
    flushdb_result = await proxy.flushdb()
    publish_result = await proxy.publish("channel", "message")
    hget_result = await proxy.hget("hash", "key")
    hset_result = await proxy.hset("hash", "key", "value")
    
    # Assert results
    assert get_result is None
    assert set_result is False
    assert delete_result == 0
    assert exists_result is False
    assert keys_result == []
    assert flushdb_result is False
    assert publish_result == 0
    assert hget_result is None
    assert hset_result == 0

@pytest.mark.asyncio
async def test_redis_error_handling(proxy: RedisProxy):
    """Test handling of Redis errors."""
    # Mock Redis operation to raise an exception
    proxy._mock_client.set.side_effect = Exception("Redis error")
    
    # Call the method
    result = await proxy.set("key", "value")
    
    # Assert it handled the error gracefully
    assert result is False

@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test handling of connection errors during startup."""
    proxy = RedisProxy(host="localhost", port=6379)
    
    with patch('redis.Redis') as mock_redis:
        # Mock client that raises exception on ping
        mock_client = MagicMock()
        mock_client.ping.side_effect = Exception("Connection error")
        mock_redis.return_value = mock_client
        
        # This should not raise an exception but log the error
        with patch.object(logging.getLogger("RedisProxy"), 'error') as mock_log:
            await proxy.start()
            mock_log.assert_called()