import pytest
import pytest_asyncio
import asyncio
import logging
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock, call

from typing import Generator, AsyncGenerator

from petal_app_manager.proxies.redis import RedisProxy, CommunicationMessage, MessagePriority, MessageStatus

@pytest_asyncio.fixture
async def proxy() -> AsyncGenerator[RedisProxy, None]:
    """Create a RedisProxy instance for testing with mocked Redis client."""
    # Create the proxy with test configuration
    proxy = RedisProxy(host="localhost", port=6379, db=0, debug=True, app_id="test-app")
    
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

@pytest_asyncio.fixture
async def communication_proxy() -> AsyncGenerator[RedisProxy, None]:
    """Create a RedisProxy instance with communication features for testing."""
    proxy = RedisProxy(host="localhost", port=6379, db=0, debug=True, app_id="test-comm-app")
    
    try:
        with patch('redis.Redis') as mock_redis:
            # Setup mock clients for both main and pubsub
            mock_client = MagicMock()
            mock_pubsub_client = MagicMock()
            mock_client.ping.return_value = True
            
            # Mock pubsub functionality
            mock_pubsub = MagicMock()
            mock_pubsub_client.pubsub.return_value = mock_pubsub
            
            def redis_side_effect(*args, **kwargs):
                if not hasattr(redis_side_effect, 'call_count'):
                    redis_side_effect.call_count = 0
                redis_side_effect.call_count += 1
                
                if redis_side_effect.call_count == 1:
                    return mock_client
                else:
                    return mock_pubsub_client
            
            mock_redis.side_effect = redis_side_effect
            
            # Store references for assertions
            proxy._mock_client = mock_client
            proxy._mock_pubsub_client = mock_pubsub_client
            proxy._mock_pubsub = mock_pubsub
            
            await proxy.start()
            yield proxy
    finally:
        try:
            if hasattr(proxy, "_client") and proxy._client:
                await proxy.stop()
        except Exception as e:
            print(f"Error during communication proxy cleanup: {e}")

@pytest.mark.asyncio
async def test_start_connection(proxy: RedisProxy):
    """Test that Redis connection is established correctly."""
    assert proxy._client is not None
    # The ping should have been called during start
    proxy._mock_client.ping.assert_called_once()

@pytest.mark.asyncio
async def test_stop_connection(proxy: RedisProxy):
    """Test that Redis connection is closed properly."""
    # Store reference to original close methods
    original_client_close = proxy._mock_client.close
    original_pubsub_close = getattr(proxy, '_mock_pubsub_client', MagicMock()).close
    
    # Replace with new mocks
    mock_client_close = MagicMock()
    mock_pubsub_close = MagicMock()
    proxy._mock_client.close = mock_client_close
    if hasattr(proxy, '_mock_pubsub_client'):
        proxy._mock_pubsub_client.close = mock_pubsub_close
    
    try:
        # Call the stop method
        await proxy.stop()
        
        # Verify the client close was called
        mock_client_close.assert_called()
        
        # If pubsub client exists, verify it was closed too
        if hasattr(proxy, '_mock_pubsub_client'):
            mock_pubsub_close.assert_called()
    finally:
        # Restore original methods
        proxy._mock_client.close = original_client_close
        if hasattr(proxy, '_mock_pubsub_client'):
            proxy._mock_pubsub_client.close = original_pubsub_close

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
    # Reset the mock to clear any previous calls made during initialization
    proxy._mock_client.hset.reset_mock()
    
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

# ------ Two-Way Communication Tests ------ #

@pytest.mark.asyncio
async def test_communication_message_creation():
    """Test CommunicationMessage creation and serialization."""
    message = CommunicationMessage(
        id="test-id",
        sender="app1",
        recipient="app2",
        message_type="test_type",
        payload={"key": "value"},
        priority=MessagePriority.HIGH
    )
    
    # Test to_dict
    data = message.to_dict()
    assert data["id"] == "test-id"
    assert data["sender"] == "app1"
    assert data["priority"] == MessagePriority.HIGH.value
    
    # Test JSON serialization
    json_str = message.to_json()
    assert isinstance(json_str, str)
    
    # Test deserialization
    restored_message = CommunicationMessage.from_json(json_str)
    assert restored_message.id == message.id
    assert restored_message.priority == message.priority

@pytest.mark.asyncio
async def test_register_message_handler(communication_proxy: RedisProxy):
    """Test registering and unregistering message handlers."""
    async def test_handler(message: CommunicationMessage) -> None:
        pass
    
    # Register handler
    await communication_proxy.register_message_handler("test_type", test_handler)
    assert "test_type" in communication_proxy._message_handlers
    
    # Unregister handler
    await communication_proxy.unregister_message_handler("test_type")
    assert "test_type" not in communication_proxy._message_handlers

@pytest.mark.asyncio
async def test_send_message(communication_proxy: RedisProxy):
    """Test sending a message."""
    # Setup mock returns
    communication_proxy._mock_client.zadd.return_value = True
    communication_proxy._mock_client.publish.return_value = 1
    communication_proxy._mock_client.hset.return_value = True
    
    # Send message
    result = await communication_proxy.send_message(
        recipient="HEAR_FC",
        message_type="command",
        payload={"action": "start", "parameters": {"mode": "auto"}},
        priority=MessagePriority.HIGH
    )
    
    # Verify calls were made
    communication_proxy._mock_client.zadd.assert_called_once()
    communication_proxy._mock_client.publish.assert_called_once()
    communication_proxy._mock_client.hset.assert_called()

@pytest.mark.asyncio
async def test_send_message_with_reply_wait(communication_proxy: RedisProxy):
    """Test sending a message and waiting for reply."""
    # Setup mocks
    communication_proxy._mock_client.zadd.return_value = True
    communication_proxy._mock_client.publish.return_value = 1
    communication_proxy._mock_client.hset.return_value = True
    
    # Mock the reply waiting by immediately fulfilling the future
    async def mock_wait_for_reply(message_id: str, timeout: int):
        reply = CommunicationMessage(
            id="reply-id",
            sender="HEAR_FC",
            recipient="test-comm-app",
            message_type="command_reply",
            payload={"status": "success"},
            reply_to=message_id
        )
        return reply
    
    communication_proxy._wait_for_reply = mock_wait_for_reply
    
    # Send message with reply wait
    reply = await communication_proxy.send_message(
        recipient="HEAR_FC",
        message_type="command",
        payload={"action": "status"},
        wait_for_reply=True,
        timeout=5
    )
    
    assert reply is not None
    assert reply.message_type == "command_reply"
    assert reply.payload["status"] == "success"

@pytest.mark.asyncio
async def test_send_reply(communication_proxy: RedisProxy):
    """Test sending a reply to a message."""
    original_message = CommunicationMessage(
        id="original-id",
        sender="HEAR_FC",
        recipient="test-comm-app",
        message_type="status_request",
        payload={"query": "health"}
    )
    
    # Setup mocks
    communication_proxy._mock_client.zadd.return_value = True
    communication_proxy._mock_client.publish.return_value = 1
    communication_proxy._mock_client.hset.return_value = True
    
    # Send reply
    result = await communication_proxy.send_reply(
        original_message,
        {"status": "healthy", "uptime": 3600}
    )
    
    assert result is not None
    communication_proxy._mock_client.zadd.assert_called_once()

@pytest.mark.asyncio
async def test_message_handler_processing(communication_proxy: RedisProxy):
    """Test message handler processing."""
    received_messages = []
    
    async def test_handler(message: CommunicationMessage) -> CommunicationMessage:
        received_messages.append(message)
        return CommunicationMessage(
            id="reply-id",
            sender="test-comm-app",
            recipient=message.sender,
            message_type="test_reply",
            payload={"received": True}
        )
    
    # Register handler
    await communication_proxy.register_message_handler("test_command", test_handler)
    
    # Setup mocks for message processing
    communication_proxy._mock_client.hset.return_value = True
    
    # Create test message
    test_message = CommunicationMessage(
        id="test-msg-id",
        sender="HEAR_FC",
        recipient="test-comm-app",
        message_type="test_command",
        payload={"data": "test"}
    )
    
    # Process the message
    await communication_proxy._handle_received_message(test_message)
    
    # Verify handler was called
    assert len(received_messages) == 1
    assert received_messages[0].message_type == "test_command"
    assert received_messages[0].payload["data"] == "test"

@pytest.mark.asyncio
async def test_get_application_status(communication_proxy: RedisProxy):
    """Test getting application status."""
    # Setup mock return
    mock_status = {
        "status": "online",
        "last_seen": str(time.time()),
        "app_id": "HEAR_FC"
    }
    communication_proxy._mock_client.hgetall.return_value = mock_status
    
    # Get status
    status = await communication_proxy.get_application_status("HEAR_FC")
    
    assert status == mock_status
    communication_proxy._mock_client.hgetall.assert_called_once_with("status:HEAR_FC")

@pytest.mark.asyncio
async def test_list_online_applications(communication_proxy: RedisProxy):
    """Test listing online applications."""
    # Setup mocks
    communication_proxy._mock_client.keys.return_value = [
        "status:HEAR_FC",
        "status:another_app",
        "status:offline_app"
    ]
    
    def mock_hget(key, field):
        if key == "status:HEAR_FC":
            return "online"
        elif key == "status:another_app":
            return "online"
        else:
            return "offline"
    
    communication_proxy._mock_client.hget.side_effect = mock_hget
    
    # Get online apps
    online_apps = await communication_proxy.list_online_applications()
    
    assert "HEAR_FC" in online_apps
    assert "another_app" in online_apps
    assert "offline_app" not in online_apps

@pytest.mark.asyncio
async def test_get_message_status(communication_proxy: RedisProxy):
    """Test getting message status."""
    # Setup mock
    communication_proxy._mock_client.hget.return_value = MessageStatus.COMPLETED.value
    
    # Get status
    status = await communication_proxy.get_message_status("test-msg-id")
    
    assert status == MessageStatus.COMPLETED.value
    communication_proxy._mock_client.hget.assert_called_once_with("message:test-msg-id", "status")

@pytest.mark.asyncio
async def test_start_stop_listening(communication_proxy: RedisProxy):
    """Test starting and stopping message listening."""
    # Start listening
    await communication_proxy.start_listening()
    assert communication_proxy._is_listening is True
    assert len(communication_proxy._subscription_tasks) > 0
    
    # Stop listening
    await communication_proxy.stop_listening()
    assert communication_proxy._is_listening is False

@pytest.mark.asyncio
async def test_inbox_queue_processing(communication_proxy: RedisProxy):
    """Test inbox queue message processing."""
    # Create test message
    test_message = CommunicationMessage(
        id="queue-msg-id",
        sender="HEAR_FC",
        recipient="test-comm-app",
        message_type="queue_test",
        payload={"queue_data": "test"}
    )
    
    # Setup mock to return message once, then empty
    call_count = 0
    def mock_zpopmax(queue_name, count):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [(test_message.to_json(), 1000)]
        return []
    
    communication_proxy._mock_client.zpopmax.side_effect = mock_zpopmax
    communication_proxy._mock_client.hset.return_value = True
    
    # Register a handler
    received_messages = []
    async def queue_handler(message: CommunicationMessage) -> None:
        received_messages.append(message)
    
    await communication_proxy.register_message_handler("queue_test", queue_handler)
    
    # Process one iteration of the queue
    communication_proxy._is_listening = True
    
    # Manually call the queue processing once
    await communication_proxy._handle_received_message(test_message)
    
    # Verify message was processed
    assert len(received_messages) == 1
    assert received_messages[0].message_type == "queue_test"

@pytest.mark.asyncio
async def test_communication_error_handling(communication_proxy: RedisProxy):
    """Test error handling in communication methods."""
    # Test send_message with Redis error
    communication_proxy._mock_client.zadd.side_effect = Exception("Redis error")
    
    result = await communication_proxy.send_message(
        recipient="HEAR_FC",
        message_type="test",
        payload={"data": "test"}
    )
    
    # Should handle error gracefully
    assert result is None
    
    # Test get_application_status with error
    communication_proxy._mock_client.hgetall.side_effect = Exception("Redis error")
    
    status = await communication_proxy.get_application_status("HEAR_FC")
    assert status is None

@pytest.mark.asyncio
async def test_client_not_initialized_communication():
    """Test communication methods when Redis client is not initialized."""
    proxy = RedisProxy(host="localhost", port=6379, app_id="test-uninit")
    
    # Test various methods without initialization
    result = await proxy.send_message("HEAR_FC", "test", {})
    assert result is None
    
    status = await proxy.get_application_status("HEAR_FC")
    assert status is None
    
    online_apps = await proxy.list_online_applications()
    assert online_apps == []
    
    msg_status = await proxy.get_message_status("test-id")
    assert msg_status is None

@pytest.mark.asyncio
async def test_message_priority_ordering():
    """Test message priority in CommunicationMessage."""
    low_msg = CommunicationMessage("1", "app1", "app2", "test", {}, MessagePriority.LOW)
    high_msg = CommunicationMessage("2", "app1", "app2", "test", {}, MessagePriority.HIGH)
    critical_msg = CommunicationMessage("3", "app1", "app2", "test", {}, MessagePriority.CRITICAL)
    
    assert low_msg.priority.value < high_msg.priority.value
    assert high_msg.priority.value < critical_msg.priority.value

@pytest.mark.asyncio
async def test_hear_fc_integration_scenario(communication_proxy: RedisProxy):
    """Test a realistic HEAR_FC communication scenario."""
    # Setup mocks for successful communication
    communication_proxy._mock_client.zadd.return_value = True
    communication_proxy._mock_client.publish.return_value = 1
    communication_proxy._mock_client.hset.return_value = True
    communication_proxy._mock_client.hgetall.return_value = {
        "status": "online",
        "last_seen": str(time.time()),
        "app_id": "HEAR_FC"
    }
    
    # 1. Check if HEAR_FC is online
    status = await communication_proxy.get_application_status("HEAR_FC")
    assert status["status"] == "online"
    
    # 2. Send configuration command to HEAR_FC
    config_result = await communication_proxy.send_message(
        recipient="HEAR_FC",
        message_type="configuration",
        payload={
            "flight_mode": "autonomous",
            "altitude_limit": 100,
            "geofence": {"lat": 37.7749, "lon": -122.4194, "radius": 1000}
        },
        priority=MessagePriority.HIGH
    )
    
    # 3. Send status request
    await communication_proxy.send_message(
        recipient="HEAR_FC",
        message_type="status_request",
        payload={"fields": ["battery", "gps", "sensors"]},
        priority=MessagePriority.NORMAL
    )
    
    # 4. Register handler for HEAR_FC telemetry
    telemetry_data = []
    async def telemetry_handler(message: CommunicationMessage) -> None:
        telemetry_data.append(message.payload)
    
    await communication_proxy.register_message_handler("telemetry", telemetry_handler)
    
    # 5. Simulate receiving telemetry from HEAR_FC
    telemetry_message = CommunicationMessage(
        id="telemetry-1",
        sender="HEAR_FC",
        recipient="test-comm-app",
        message_type="telemetry",
        payload={
            "timestamp": time.time(),
            "battery_level": 85,
            "gps_status": "good",
            "altitude": 50,
            "speed": 5.2
        }
    )
    
    await communication_proxy._handle_received_message(telemetry_message)
    
    # Verify telemetry was received and processed
    assert len(telemetry_data) == 1
    assert telemetry_data[0]["battery_level"] == 85
    
    # Verify all Redis operations were called
    assert communication_proxy._mock_client.zadd.call_count >= 2  # At least 2 messages sent
    assert communication_proxy._mock_client.publish.call_count >= 2  # Notifications sent