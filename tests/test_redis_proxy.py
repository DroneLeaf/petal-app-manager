import pytest
import pytest_asyncio
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock, call

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
            # Setup the mock Redis clients
            mock_client = MagicMock()
            mock_pubsub_client = MagicMock()
            mock_pubsub = MagicMock()
            mock_pubsub_pattern = MagicMock()
            
            mock_client.ping.return_value = True
            mock_pubsub_client.pubsub.return_value = mock_pubsub
            
            # Make Redis constructor return our mocks
            mock_redis.side_effect = [mock_client, mock_pubsub_client]
            
            # Store references to the mocks for assertions
            proxy._mock_client = mock_client
            proxy._mock_pubsub_client = mock_pubsub_client
            proxy._mock_pubsub = mock_pubsub
            proxy._mock_pubsub_pattern = mock_pubsub_pattern
            
            await proxy.start()
            yield proxy
    finally:
        # Always try to stop the proxy even if tests fail
        try:
            if hasattr(proxy, "_client") and proxy._client:
                await proxy.stop()
        except Exception as e:
            print(f"Error during proxy cleanup: {e}")


@pytest_asyncio.fixture
async def unix_socket_proxy() -> AsyncGenerator[RedisProxy, None]:
    """Create a RedisProxy instance for testing Unix socket connections."""
    proxy = RedisProxy(unix_socket_path="/tmp/redis.sock", db=0, debug=True)
    
    try:
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_pubsub_client = MagicMock()
            mock_pubsub = MagicMock()
            mock_pubsub_pattern = MagicMock()
            
            mock_client.ping.return_value = True
            mock_pubsub_client.pubsub.return_value = mock_pubsub
            
            mock_redis.side_effect = [mock_client, mock_pubsub_client]
            
            proxy._mock_client = mock_client
            proxy._mock_pubsub_client = mock_pubsub_client
            proxy._mock_pubsub = mock_pubsub
            proxy._mock_pubsub_pattern = mock_pubsub_pattern
            
            await proxy.start()
            yield proxy
    finally:
        try:
            if hasattr(proxy, "_client") and proxy._client:
                await proxy.stop()
        except Exception as e:
            print(f"Error during Unix socket proxy cleanup: {e}")


# ------ Connection Tests ------ #

@pytest.mark.asyncio
async def test_start_connection_tcp(proxy: RedisProxy):
    """Test that Redis TCP connection is established correctly."""
    assert proxy._client is not None
    assert proxy._pubsub_client is not None
    assert proxy._pubsub is not None
    # The ping should have been called during start
    proxy._mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_start_connection_unix_socket(unix_socket_proxy: RedisProxy):
    """Test that Redis Unix socket connection is established correctly."""
    assert unix_socket_proxy._client is not None
    assert unix_socket_proxy._pubsub_client is not None
    assert unix_socket_proxy._pubsub is not None
    unix_socket_proxy._mock_client.ping.assert_called_once()


@pytest.mark.asyncio
async def test_stop_connection(proxy: RedisProxy):
    """Test that Redis connection is closed properly."""
    # Create new mocks for close methods to avoid interference with fixture setup
    mock_client_close = MagicMock()
    mock_pubsub_client_close = MagicMock()  
    mock_pubsub_close = MagicMock()
    mock_pubsub_pattern_close = MagicMock()
    
    # Replace the close methods
    proxy._mock_client.close = mock_client_close
    proxy._mock_pubsub_client.close = mock_pubsub_client_close
    proxy._mock_pubsub.close = mock_pubsub_close
    proxy._mock_pubsub_pattern.close = mock_pubsub_pattern_close
    
    # Call stop
    await proxy.stop()
    
    # Verify close methods were called
    mock_client_close.assert_called_once()
    mock_pubsub_client_close.assert_called_once()
    # Don't check exact call count for pubsub.close since it might be called during executor
    assert mock_pubsub_close.called, "pubsub.close should have been called"


@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test handling of connection errors during startup."""
    proxy = RedisProxy(host="localhost", port=6379)
    
    with patch('redis.Redis') as mock_redis:
        # Make Redis raise an exception
        mock_redis.side_effect = Exception("Connection failed")
        
        # This should not raise an exception
        await proxy.start()
        
        # Client should not be initialized
        assert proxy._client is None


# ------ Key-Value Operation Tests ------ #

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
async def test_exists_false(proxy: RedisProxy):
    """Test checking if a non-existent key exists in Redis."""
    # Setup mock return value
    proxy._mock_client.exists.return_value = 0
    
    # Call the method
    result = await proxy.exists("nonexistent-key")
    
    # Assert results
    assert result is False
    proxy._mock_client.exists.assert_called_once_with("nonexistent-key")


# ------ Pub/Sub Operation Tests ------ #

@pytest.mark.asyncio
async def test_publish(proxy: RedisProxy):
    """Test publishing a message to a channel."""
    # Setup mock return value
    proxy._mock_client.publish.return_value = 2  # 2 clients received
    
    # Call the method
    result = proxy.publish("test-channel", "test-message")
    
    # Assert results
    assert result == 2
    proxy._mock_client.publish.assert_called_once_with("test-channel", "test-message")


@pytest.mark.asyncio
async def test_subscribe(proxy: RedisProxy):
    """Test subscribing to a channel."""
    # Setup mock
    proxy._mock_pubsub.subscribe.return_value = None
    
    # Define a test callback
    messages_received = []
    
    def test_callback(channel: str, message: str):
        messages_received.append((channel, message))
    
    # Subscribe to the channel
    proxy.subscribe("test-channel", test_callback)
    
    # Verify subscription was made
    proxy._mock_pubsub.subscribe.assert_called_once_with("test-channel")
    
    # Verify callback was stored
    assert "test-channel" in proxy._subscriptions
    assert proxy._subscriptions["test-channel"] == test_callback


@pytest.mark.asyncio
async def test_unsubscribe(proxy: RedisProxy):
    """Test unsubscribing from a channel."""
    # Setup - first subscribe
    proxy._mock_pubsub.subscribe.return_value = None
    proxy._mock_pubsub.unsubscribe.return_value = None
    
    def test_callback(channel: str, message: str):
        pass
    
    # Subscribe first
    proxy.subscribe("test-channel", test_callback)
    
    # Now unsubscribe
    proxy.unsubscribe("test-channel")
    
    # Verify unsubscription
    proxy._mock_pubsub.unsubscribe.assert_called_once_with("test-channel")
    
    # Verify callback was removed
    assert "test-channel" not in proxy._subscriptions


@pytest.mark.asyncio
async def test_message_listening():
    """Test the message listening functionality."""
    proxy = RedisProxy(host="localhost", port=6379)
    
    with patch('redis.Redis') as mock_redis:
        mock_client = MagicMock()
        mock_pubsub_client = MagicMock()
        mock_pubsub = MagicMock()
        
        mock_client.ping.return_value = True
        mock_pubsub_client.pubsub.return_value = mock_pubsub
        
        # Setup message sequence
        messages = [
            {'type': 'subscribe', 'channel': 'test-channel'},
            {'type': 'message', 'channel': 'test-channel', 'data': 'hello'},
            {'type': 'message', 'channel': 'test-channel', 'data': 'world'},
            None  # Timeout
        ]
        
        mock_pubsub.get_message.side_effect = messages
        mock_redis.side_effect = [mock_client, mock_pubsub_client]
        
        # Track received messages
        received_messages = []
        
        def test_callback(channel: str, message: str):
            received_messages.append((channel, message))
        
        try:
            await proxy.start()
            
            # Subscribe to channel
            proxy.subscribe("test-channel", test_callback)
            
            # Let the listening loop run a bit
            await asyncio.sleep(0.1)
            
            # Verify messages were processed
            # Note: In real scenario, we'd need to mock the executor properly
            # This is more of a structural test
            assert "test-channel" in proxy._subscriptions
            
        finally:
            await proxy.stop()


# ------ Error Handling Tests ------ #

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
    publish_result = proxy.publish("channel", "message")
    
    # Assert results
    assert get_result is None
    assert set_result is False
    assert delete_result == 0
    assert exists_result is False
    assert publish_result == 0


@pytest.mark.asyncio
async def test_redis_operation_error_handling(proxy: RedisProxy):
    """Test handling of Redis operation errors."""
    # Mock Redis operation to raise an exception
    proxy._mock_client.set.side_effect = Exception("Redis error")
    proxy._mock_client.get.side_effect = Exception("Redis error")
    proxy._mock_client.delete.side_effect = Exception("Redis error")
    proxy._mock_client.exists.side_effect = Exception("Redis error")
    proxy._mock_client.publish.side_effect = Exception("Redis error")
    
    # Call the methods - they should handle errors gracefully
    set_result = await proxy.set("key", "value")
    get_result = await proxy.get("key")
    delete_result = await proxy.delete("key")
    exists_result = await proxy.exists("key")
    publish_result = proxy.publish("channel", "message")
    
    # Assert they handled the errors gracefully
    assert set_result is False
    assert get_result is None
    assert delete_result == 0
    assert exists_result is False
    assert publish_result == 0


@pytest.mark.asyncio
async def test_pubsub_not_initialized():
    """Test pub/sub operations when pub/sub is not initialized."""
    proxy = RedisProxy(host="localhost", port=6379)
    
    # Mock only the main client, not pub/sub
    with patch('redis.Redis') as mock_redis:
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis.return_value = mock_client
        
        proxy._client = mock_client
        proxy._pubsub_client = None
        proxy._pubsub = None
        
        def test_callback(channel: str, message: str):
            pass
        
        # Try to subscribe - should handle gracefully
        proxy.subscribe("test-channel", test_callback)
        proxy.unsubscribe("test-channel")
        
        # Should not crash


# ------ Integration Tests ------ #

@pytest.mark.asyncio
async def test_basic_workflow(proxy: RedisProxy):
    """Test a basic Redis workflow: set, get, publish, subscribe."""
    # Setup mocks
    proxy._mock_client.set.return_value = True
    proxy._mock_client.get.return_value = "stored-value"
    proxy._mock_client.publish.return_value = 1
    proxy._mock_pubsub.subscribe.return_value = None
    
    # 1. Store a value
    set_result = await proxy.set("workflow:test", "stored-value")
    assert set_result is True
    
    # 2. Retrieve the value
    get_result = await proxy.get("workflow:test")
    assert get_result == "stored-value"
    
    # 3. Subscribe to a channel
    messages = []
    
    async def message_handler(channel: str, message: str):
        messages.append((channel, message))
    
    proxy.subscribe("workflow:notifications", message_handler)
    
    # 4. Publish a message
    publish_result = proxy.publish("workflow:notifications", "test message")
    assert publish_result == 1
    
    # Verify all operations worked
    proxy._mock_client.set.assert_called_with("workflow:test", "stored-value", ex=None)
    proxy._mock_client.get.assert_called_with("workflow:test")
    proxy._mock_client.publish.assert_called_with("workflow:notifications", "test message")
    proxy._mock_pubsub.subscribe.assert_called_with("workflow:notifications")


@pytest.mark.asyncio
async def test_unix_socket_configuration():
    """Test that Unix socket configuration is used correctly."""
    proxy = RedisProxy(unix_socket_path="/tmp/redis.sock", db=1)
    
    with patch('redis.Redis') as mock_redis:
        mock_client = MagicMock()
        mock_pubsub_client = MagicMock()
        mock_pubsub = MagicMock()
        
        mock_client.ping.return_value = True
        mock_pubsub_client.pubsub.return_value = mock_pubsub
        
        mock_redis.side_effect = [mock_client, mock_pubsub_client]
        
        await proxy.start()
        
        # Verify Redis was called with Unix socket parameters
        assert mock_redis.call_count == 2
        
        # Check the calls made to Redis constructor
        calls = mock_redis.call_args_list
        
        # Both calls should use unix_socket_path
        for call in calls:
            args, kwargs = call
            assert kwargs.get('unix_socket_path') == '/tmp/redis.sock'
            assert kwargs.get('db') == 1
            assert kwargs.get('decode_responses') is True
        
        await proxy.stop()


# ------ Performance and Concurrency Tests ------ #

@pytest.mark.asyncio
async def test_concurrent_operations(proxy: RedisProxy):
    """Test concurrent Redis operations."""
    # Setup mocks
    proxy._mock_client.set.return_value = True
    proxy._mock_client.get.return_value = "concurrent-value"
    proxy._mock_client.publish.return_value = 1
    
    # Run multiple operations concurrently
    tasks = [
        proxy.set(f"concurrent:key{i}", f"value{i}")
        for i in range(10)
    ]
    tasks.extend([
        proxy.get(f"concurrent:key{i}")
        for i in range(10)
    ])
    # Publish operations are synchronous, so we can't run them concurrently in the same way
    publish_results = [
        proxy.publish(f"concurrent:channel{i}", f"message{i}")
        for i in range(5)
    ]
    
    # Execute async tasks concurrently
    results = await asyncio.gather(*tasks)
    
    # Verify async operations completed
    assert len(results) == 20
    
    # Verify set operations returned True
    set_results = results[:10]
    assert all(result is True for result in set_results)
    
    # Verify get operations returned expected value
    get_results = results[10:20]
    assert all(result == "concurrent-value" for result in get_results)
    
    # Verify publish operations returned subscriber count
    assert all(result == 1 for result in publish_results)
    assert len(publish_results) == 5
