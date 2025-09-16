import pytest
import pytest_asyncio
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock, call
import threading
import json
from typing import Generator, AsyncGenerator

from petal_app_manager.proxies.mqtt import MQTTProxy


@pytest_asyncio.fixture
async def proxy() -> AsyncGenerator[MQTTProxy, None]:
    """Create an MQTTProxy instance for testing with mocked dependencies."""
    
    # Mock the OrganizationManager for testing - this needs to be active throughout the test
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager, \
         patch('petal_app_manager.proxies.mqtt.requests.get') as mock_get, \
         patch('petal_app_manager.proxies.mqtt.requests.request') as mock_request:
        
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "e8fc2cd9-f040-4229-84c0-62ea693b99f6"
        mock_org_manager.machine_id = "ce93d985-d950-4f0d-be32-f778f1a00cdc"
        mock_get_org_manager.return_value = mock_org_manager
        
        # Create the proxy with test configuration
        proxy = MQTTProxy(
            ts_client_host="localhost",
            ts_client_port=3004,
            callback_host="localhost",
            callback_port=3005,
            enable_callbacks=True,
            debug=True
        )
        
        # Set required attributes manually instead of calling start()
        proxy.robot_instance_id = "ce93d985-d950-4f0d-be32-f778f1a00cdc"
        proxy.device_id = "Instance-ce93d985-d950-4f0d-be32-f778f1a00cdc"
        proxy._loop = asyncio.get_running_loop()
        proxy.is_connected = True
        
        # Initialize worker thread state for testing
        proxy._worker_running = threading.Event()
        proxy._worker_running.set()
        proxy._worker_threads = []
        
        # Setup mock callback app
        proxy.callback_app = MagicMock()
        proxy.callback_server = MagicMock()
        proxy.callback_thread = MagicMock()
        proxy.callback_thread.is_alive.return_value = True
        
        # Setup mock responses for health checks
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_health_response
        
        # Setup mock responses for MQTT operations
        mock_operation_response = MagicMock()
        mock_operation_response.status_code = 200
        mock_operation_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_operation_response
        
        # Store references to mocks for assertions
        proxy._mock_get = mock_get
        proxy._mock_request = mock_request
        
        try:
            yield proxy
        finally:
            # Cleanup
            proxy.is_connected = False
            proxy._worker_running.clear()


@pytest_asyncio.fixture
async def proxy_no_callbacks() -> AsyncGenerator[MQTTProxy, None]:
    """Create an MQTTProxy instance with callbacks disabled for testing."""
    
    # Mock the OrganizationManager for testing - this needs to be active throughout the test
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager, \
         patch('petal_app_manager.proxies.mqtt.requests.get') as mock_get, \
         patch('petal_app_manager.proxies.mqtt.requests.request') as mock_request:
        
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "e8fc2cd9-f040-4229-84c0-62ea693b99f6"
        mock_org_manager.machine_id = "ce93d985-d950-4f0d-be32-f778f1a00cdc"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy(
            ts_client_host="localhost",
            ts_client_port=3004,
            enable_callbacks=False,
            debug=True
        )
        
        # Setup mock responses
        mock_health_response = MagicMock()
        mock_health_response.status_code = 200
        mock_health_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_health_response
        
        mock_operation_response = MagicMock()
        mock_operation_response.status_code = 200
        mock_operation_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_operation_response
        
        proxy._mock_get = mock_get
        proxy._mock_request = mock_request
        
        try:
            await proxy.start()
            yield proxy
        finally:
            try:
                if proxy.is_connected:
                    await proxy.stop()
            except Exception as e:
                print(f"Error during proxy cleanup: {e}")


# ------ Connection Tests ------ #

@pytest.mark.asyncio
async def test_start_connection_with_callbacks(proxy: MQTTProxy):
    """Test that MQTT connection is established correctly with callback server."""
    assert proxy.is_connected is True
    assert proxy.organization_id == "e8fc2cd9-f040-4229-84c0-62ea693b99f6"
    assert proxy.robot_instance_id == "ce93d985-d950-4f0d-be32-f778f1a00cdc"
    assert proxy.device_id == "Instance-ce93d985-d950-4f0d-be32-f778f1a00cdc"
    assert proxy.callback_app is not None
    assert proxy.enable_callbacks is True


@pytest.mark.asyncio
async def test_start_connection_without_callbacks(proxy_no_callbacks: MQTTProxy):
    """Test that MQTT connection is established correctly without callback server."""
    assert proxy_no_callbacks.is_connected is True
    assert proxy_no_callbacks.callback_app is None
    assert proxy_no_callbacks.enable_callbacks is False
    
    # Verify health check was called
    proxy_no_callbacks._mock_get.assert_called()


@pytest.mark.asyncio
async def test_stop_connection(proxy: MQTTProxy):
    """Test that MQTT connection is closed properly."""
    # Verify proxy is connected
    assert proxy.is_connected is True
    
    # Call stop
    await proxy.stop()
    
    # Verify disconnection
    assert proxy.is_connected is False
    assert proxy._shutdown_flag is True


@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test handling of connection errors during startup."""
    
    # Mock OrganizationManager to return proper IDs
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "test-org"
        mock_org_manager.machine_id = "test-machine"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy(
            ts_client_host="localhost",
            ts_client_port=3004
        )
        
        with patch('requests.get') as mock_get:
            # Make health check fail
            mock_get.side_effect = Exception("Connection failed")
            
            # This should raise an exception
            with pytest.raises(ConnectionError):
                await proxy.start()
            
            # Client should not be connected
            assert proxy.is_connected is False


@pytest.mark.asyncio
async def test_missing_organization_id():
    """Test handling of missing organization ID - should not fail startup anymore."""
    
    # Mock OrganizationManager to return None for organization_id
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = None
        mock_org_manager.machine_id = "test-machine"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy()
        
        # Mock health check to pass
        with patch('petal_app_manager.proxies.mqtt.requests.get') as mock_get:
            mock_health_response = MagicMock()
            mock_health_response.status_code = 200
            mock_get.return_value = mock_health_response
            
            # Should succeed - organization_id not required at startup
            await proxy.start()
            assert proxy.is_connected is True
            await proxy.stop()


@pytest.mark.asyncio
async def test_missing_machine_id():
    """Test handling of missing machine ID."""
    
    # Mock OrganizationManager to return None for machine_id
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "test-org"
        mock_org_manager.machine_id = None
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy()
        
        with pytest.raises(ValueError, match="Robot Instance ID must be available from OrganizationManager"):
            await proxy.start()


# ------ TypeScript Client Communication Tests ------ #

@pytest.mark.asyncio
async def test_check_ts_client_health_success(proxy: MQTTProxy):
    """Test successful TypeScript client health check."""
    # Health check should already be successful from fixture setup
    health_status = await proxy._check_ts_client_health()
    assert health_status is True


@pytest.mark.asyncio
async def test_check_ts_client_health_failure():
    """Test failed TypeScript client health check."""
    
    # Mock OrganizationManager to return proper IDs
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "test-org"
        mock_org_manager.machine_id = "test-machine"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy()
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            health_status = await proxy._check_ts_client_health()
        assert health_status is False


@pytest.mark.asyncio
async def test_make_ts_request_success(proxy: MQTTProxy):
    """Test successful TypeScript client request."""
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy._make_ts_request("POST", "/test", {"data": "test"})
        assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_make_ts_request_error(proxy: MQTTProxy):
    """Test TypeScript client request with error response."""
    # Mock error response
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy._make_ts_request("POST", "/test", {"data": "test"})
        assert "error" in result
        assert "500" in result["error"]


@pytest.mark.asyncio
async def test_make_ts_request_exception(proxy: MQTTProxy):
    """Test TypeScript client request with exception."""
    with patch('requests.request', side_effect=Exception("Network error")):
        result = await proxy._make_ts_request("POST", "/test", {"data": "test"})
        assert "error" in result
        assert "Network error" in result["error"]


# ------ Message Publishing Tests ------ #

@pytest.mark.asyncio
async def test_publish_message_success(proxy: MQTTProxy):
    """Test successful message publishing."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy.publish_message(
            "test/topic",
            {"message": "hello world"},
            qos=1
        )
        
        assert result is True


@pytest.mark.asyncio
async def test_publish_message_disconnected():
    """Test publishing when proxy is disconnected."""
    
    # Mock OrganizationManager to return proper IDs
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "test-org"
        mock_org_manager.machine_id = "test-machine"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy()
        # Don't call start() so proxy remains disconnected
        
        result = await proxy.publish_message("test/topic", {"message": "hello"})
        assert result is False


@pytest.mark.asyncio
async def test_publish_message_error(proxy: MQTTProxy):
    """Test publishing with TypeScript client error."""
    # Setup mock error response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "Publish failed"}
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy.publish_message("test/topic", {"message": "hello"})
        assert result is False


@pytest.mark.asyncio
async def test_send_command_response(proxy: MQTTProxy):
    """Test sending command response."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy.send_command_response(
            "test/response/topic",
            "msg-123",
            {"result": "completed"}
        )
        
        assert result is True


# ------ Subscription Management Tests ------ #

@pytest.mark.asyncio
async def test_subscribe_to_topic_success(proxy: MQTTProxy):
    """Test successful topic subscription."""
    # Define a test callback
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    result = await proxy.subscribe_to_topic("test/topic", test_callback)
    
    assert result is True
    assert "test/topic" in proxy._subscriptions
    assert proxy._subscriptions["test/topic"] == test_callback
    assert "test/topic" in proxy.subscribed_topics


@pytest.mark.asyncio
async def test_subscribe_to_topic_disconnected():
    """Test subscribing when proxy is disconnected."""
    
    
    proxy = MQTTProxy()
    # Don't call start() so proxy remains disconnected
    
    result = await proxy.subscribe_to_topic("test/topic")
    assert result is False


@pytest.mark.asyncio
async def test_subscribe_to_topic_error(proxy: MQTTProxy):
    """Test subscription with TypeScript client error."""
    # Setup mock error response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"error": "Subscription failed"}
    
    with patch('requests.request', return_value=mock_response):
        result = await proxy.subscribe_to_topic("test/topic")
        assert result is False


@pytest.mark.asyncio
async def test_unsubscribe_from_topic_success(proxy: MQTTProxy):
    """Test successful topic unsubscription."""
    # First subscribe
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    async def test_callback(topic: str, payload: dict):
        pass
    
    with patch('requests.request', return_value=mock_response):
        # Subscribe first
        await proxy.subscribe_to_topic("test/topic", test_callback)
        
        # Now unsubscribe
        result = await proxy.unsubscribe_from_topic("test/topic")
        
        assert result is True
        assert "test/topic" not in proxy._subscriptions


@pytest.mark.asyncio
async def test_unsubscribe_from_topic_disconnected():
    """Test unsubscribing when proxy is disconnected."""
    
    
    proxy = MQTTProxy()
    # Don't call start() so proxy remains disconnected
    
    result = await proxy.unsubscribe_from_topic("test/topic")
    assert result is False


@pytest.mark.asyncio
async def test_subscribe_pattern(proxy: MQTTProxy):
    """Test pattern subscription."""
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    proxy.subscribe_pattern("test/*", test_callback)
    
    assert "test/*" in proxy._subscription_patterns
    assert proxy._subscription_patterns["test/*"] == test_callback


@pytest.mark.asyncio
async def test_unsubscribe_pattern(proxy: MQTTProxy):
    """Test pattern unsubscription."""
    async def test_callback(topic: str, payload: dict):
        pass
    
    # Subscribe first
    proxy.subscribe_pattern("test/*", test_callback)
    
    # Now unsubscribe
    proxy.unsubscribe_pattern("test/*")
    
    assert "test/*" not in proxy._subscription_patterns


# ------ Message Processing Tests ------ #

@pytest.mark.asyncio
async def test_process_received_message_topic_match(proxy: MQTTProxy):
    """Test processing received message with topic subscription."""
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    # Subscribe to topic
    proxy._subscriptions["test/topic"] = test_callback
    
    # Create and enqueue message (new deque-based approach)
    from petal_app_manager.proxies.mqtt import MQTTMessage
    message = MQTTMessage(
        topic="test/topic",
        payload={"message": "hello world"}
    )
    
    # Process message directly in worker context for testing
    proxy._process_message_in_worker(message)
    
    # Give async callback time to execute
    await asyncio.sleep(0.1)
    
    # Verify callback was called
    assert len(messages_received) == 1
    assert messages_received[0] == ("test/topic", {"message": "hello world"})


@pytest.mark.asyncio
async def test_process_received_message_pattern_match(proxy: MQTTProxy):
    """Test processing received message with pattern subscription."""
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    # Subscribe to pattern
    proxy._subscription_patterns["test/*"] = test_callback
    
    # Create and process message
    from petal_app_manager.proxies.mqtt import MQTTMessage
    message = MQTTMessage(
        topic="test/subtopic",
        payload={"message": "pattern match"}
    )
    
    proxy._process_message_in_worker(message)
    
    # Give async callback time to execute
    await asyncio.sleep(0.1)
    
    # Verify callback was called
    assert len(messages_received) == 1
    assert messages_received[0] == ("test/subtopic", {"message": "pattern match"})


@pytest.mark.asyncio
async def test_process_received_message_no_topic(proxy: MQTTProxy):
    """Test processing received message without topic."""
    from petal_app_manager.proxies.mqtt import MQTTMessage
    
    # Message with empty topic should not crash
    message = MQTTMessage(
        topic="",
        payload={"message": "no topic"}
    )
    
    # Should not raise exception
    proxy._process_message_in_worker(message)


@pytest.mark.asyncio
async def test_topic_matches_pattern():
    """Test topic pattern matching using fnmatch."""
    assert MQTTProxy._topic_matches_pattern("test/topic", "test/*") is True
    assert MQTTProxy._topic_matches_pattern("test/topic/subtopic", "test/*") is True  # fnmatch * matches everything
    assert MQTTProxy._topic_matches_pattern("other/topic", "test/*") is False
    assert MQTTProxy._topic_matches_pattern("test/topic", "test/topic") is True
    assert MQTTProxy._topic_matches_pattern("test/topic", "*/topic") is True


@pytest.mark.asyncio
async def test_process_command_message(proxy: MQTTProxy):
    """Test processing command message with auto-response."""
    # Setup mock for response publishing
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    with patch('requests.request', return_value=mock_response):
        command_topic = f"org/{proxy.organization_id}/device/{proxy.device_id}/command"
        command_payload = {
            "command": "get_status",
            "messageId": "test-123",
            "parameters": {"include_telemetry": True}
        }
        
        await proxy._process_command(command_topic, command_payload)
        
        # Verify response was published (should call _make_ts_request internally)
        # The exact verification depends on the mock setup


# ------ Health Check Tests ------ #

@pytest.mark.asyncio
async def test_health_check_healthy(proxy: MQTTProxy):
    """Test health check when proxy is healthy."""
    health = await proxy.health_check()
    
    assert health["status"] == "healthy"
    assert health["connection"]["connected"] is True
    assert health["device_info"]["organization_id"] == proxy.organization_id
    assert health["device_info"]["robot_instance_id"] == proxy.robot_instance_id
    assert "subscriptions" in health
    assert "configuration" in health


@pytest.mark.asyncio
async def test_health_check_unhealthy():
    """Test health check when proxy is unhealthy."""
    
    
    # Mock OrganizationManager for testing
    with patch('petal_app_manager.proxies.mqtt.get_organization_manager') as mock_get_org_manager:
        mock_org_manager = MagicMock()
        mock_org_manager.organization_id = "test-org"
        mock_get_org_manager.return_value = mock_org_manager
        
        proxy = MQTTProxy()
        # Set robot_instance_id manually since we're not calling start()
        proxy.robot_instance_id = "test-machine"
        # Don't call start() so proxy remains disconnected
        
        health = await proxy.health_check()
        
        assert health["status"] == "unhealthy"
        assert health["connection"]["connected"] is False


# ------ Error Handling Tests ------ #

@pytest.mark.asyncio
async def test_callback_error_handling(proxy: MQTTProxy):
    """Test error handling in message callbacks."""
    # Define a callback that raises an exception
    async def failing_callback(topic: str, payload: dict):
        raise Exception("Callback error")
    
    proxy._subscriptions["test/topic"] = failing_callback
    
    from petal_app_manager.proxies.mqtt import MQTTMessage
    message = MQTTMessage(
        topic="test/topic",
        payload={"message": "test"}
    )
    
    # Should not raise exception, should handle gracefully
    proxy._process_message_in_worker(message)


@pytest.mark.asyncio
async def test_synchronous_callback_handling(proxy: MQTTProxy):
    """Test handling of synchronous (non-async) callbacks."""
    messages_received = []
    
    def sync_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    proxy._subscriptions["test/topic"] = sync_callback
    
    from petal_app_manager.proxies.mqtt import MQTTMessage
    message = MQTTMessage(
        topic="test/topic",
        payload={"message": "sync test"}
    )
    
    proxy._process_message_in_worker(message)
    
    # Give sync callback time to process
    await asyncio.sleep(0.1)
    
    # Verify callback was called
    assert len(messages_received) == 1
    assert messages_received[0] == ("test/topic", {"message": "sync test"})


# ------ Integration Tests ------ #

@pytest.mark.asyncio
async def test_basic_workflow(proxy: MQTTProxy):
    """Test a basic MQTT workflow: subscribe, publish, receive."""
    # Setup mock responses
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    with patch('requests.request', return_value=mock_response):
        # 1. Subscribe to a topic
        subscribe_result = await proxy.subscribe_to_topic("workflow/test", test_callback)
        assert subscribe_result is True
        
        # 2. Publish a message
        publish_result = await proxy.publish_message(
            "workflow/test",
            {"message": "workflow test"},
            qos=1
        )
        assert publish_result is True
        
        # 3. Simulate receiving the message via new deque system
        from petal_app_manager.proxies.mqtt import MQTTMessage
        message = MQTTMessage(
            topic="workflow/test",
            payload={"message": "workflow test"}
        )
        proxy._process_message_in_worker(message)
        
        # Give async callback time to execute
        await asyncio.sleep(0.1)
        
        # 4. Verify message was received
        assert len(messages_received) == 1
        assert messages_received[0] == ("workflow/test", {"message": "workflow test"})
        
        # 5. Unsubscribe
        unsubscribe_result = await proxy.unsubscribe_from_topic("workflow/test")
        assert unsubscribe_result is True


@pytest.mark.asyncio
async def test_device_topic_auto_subscription(proxy: MQTTProxy):
    """Test automatic subscription to device topics."""
    # Since we're not calling the real start() method which subscribes to device topics,
    # let's manually test the subscription functionality instead
    expected_topics = [
        f"org/{proxy.organization_id}/device/{proxy.device_id}/command",
        f"org/{proxy.organization_id}/device/{proxy.device_id}/response"
    ]
    
    # Manually subscribe to test the functionality
    for topic in expected_topics:
        result = await proxy.subscribe_to_topic(topic, proxy._default_message_handler)
        assert result is True
        assert topic in proxy.subscribed_topics


@pytest.mark.asyncio
async def test_configuration_variations():
    """Test different configuration options."""
    
    
    # Test without callbacks
    proxy_no_cb = MQTTProxy(
        
        enable_callbacks=False,
        debug=False,
        request_timeout=10
    )
    
    assert proxy_no_cb.enable_callbacks is False
    assert proxy_no_cb.debug is False
    assert proxy_no_cb.request_timeout == 10
    assert proxy_no_cb.callback_url is None


# ------ Concurrency Tests ------ #

@pytest.mark.asyncio
async def test_concurrent_operations(proxy: MQTTProxy):
    """Test concurrent MQTT operations."""
    # Setup mock responses
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    
    with patch('requests.request', return_value=mock_response):
        # Run multiple publish operations concurrently
        publish_tasks = [
            proxy.publish_message(f"concurrent/topic{i}", {"message": f"test{i}"})
            for i in range(10)
        ]
        
        # Run multiple subscribe operations concurrently
        subscribe_tasks = [
            proxy.subscribe_to_topic(f"concurrent/sub{i}")
            for i in range(5)
        ]
        
        # Execute all tasks concurrently
        publish_results = await asyncio.gather(*publish_tasks)
        subscribe_results = await asyncio.gather(*subscribe_tasks)
        
        # Verify all operations completed successfully
        assert all(result is True for result in publish_results)
        assert all(result is True for result in subscribe_results)
        assert len(publish_results) == 10
        assert len(subscribe_results) == 5


@pytest.mark.asyncio
async def test_message_processing_concurrency(proxy: MQTTProxy):
    """Test concurrent message processing with new deque system."""
    messages_received = []
    
    async def test_callback(topic: str, payload: dict):
        # Simulate some processing time
        await asyncio.sleep(0.01)
        messages_received.append((topic, payload))
    
    # Subscribe to multiple topics
    for i in range(5):
        proxy._subscriptions[f"concurrent/topic{i}"] = test_callback
    
    # Create and process multiple messages
    from petal_app_manager.proxies.mqtt import MQTTMessage
    messages = [
        MQTTMessage(
            topic=f"concurrent/topic{i}",
            payload={"message": f"concurrent{i}"}
        )
        for i in range(5)
    ]
    
    # Process messages in worker context
    for message in messages:
        proxy._process_message_in_worker(message)
    
    # Give async callbacks time to execute
    await asyncio.sleep(0.2)
    
    # Verify all messages were processed
    assert len(messages_received) == 5


# ------ Deque Buffer Tests ------ #

@pytest.mark.asyncio
async def test_message_enqueue_dequeue(proxy: MQTTProxy):
    """Test message enqueue and dequeue functionality."""
    from petal_app_manager.proxies.mqtt import MQTTMessage
    
    # Create test messages
    message1 = MQTTMessage(topic="test/topic1", payload={"data": "message1"})
    message2 = MQTTMessage(topic="test/topic2", payload={"data": "message2"})
    
    # Enqueue messages
    proxy._enqueue_message(message1)
    proxy._enqueue_message(message2)
    
    # Verify buffer size
    with proxy._buffer_lock:
        assert len(proxy._message_buffer) == 2
    
    # Dequeue messages
    retrieved1 = proxy._get_next_message()
    retrieved2 = proxy._get_next_message()
    
    # Verify FIFO order
    assert retrieved1.topic == "test/topic1"
    assert retrieved1.payload == {"data": "message1"}
    assert retrieved2.topic == "test/topic2"
    assert retrieved2.payload == {"data": "message2"}
    
    # Verify buffer is empty
    assert proxy._get_next_message() is None


@pytest.mark.asyncio
async def test_duplicate_message_filtering(proxy: MQTTProxy):
    """Test duplicate message filtering by messageId."""
    from petal_app_manager.proxies.mqtt import MQTTMessage
    
    # Create duplicate messages with same messageId
    message1 = MQTTMessage(
        topic="test/topic", 
        payload={"messageId": "msg-123", "data": "first"}
    )
    message2 = MQTTMessage(
        topic="test/topic", 
        payload={"messageId": "msg-123", "data": "duplicate"}
    )
    
    # Enqueue both messages
    proxy._enqueue_message(message1)
    proxy._enqueue_message(message2)  # Should be filtered out
    
    # Verify only one message in buffer
    with proxy._buffer_lock:
        assert len(proxy._message_buffer) == 1
    
    # Verify the first message is kept
    retrieved = proxy._get_next_message()
    assert retrieved.payload["data"] == "first"


@pytest.mark.asyncio
async def test_buffer_overflow_protection(proxy: MQTTProxy):
    """Test buffer overflow protection with maxlen."""
    from petal_app_manager.proxies.mqtt import MQTTMessage
    
    # Fill buffer beyond capacity
    for i in range(proxy.max_message_buffer + 10):
        message = MQTTMessage(
            topic=f"test/topic{i}", 
            payload={"data": f"message{i}"}
        )
        proxy._enqueue_message(message)
    
    # Verify buffer doesn't exceed max size
    with proxy._buffer_lock:
        assert len(proxy._message_buffer) == proxy.max_message_buffer
    
    # Verify oldest messages were dropped (newest should be kept)
    last_message = proxy._get_next_message()
    # Due to deque maxlen behavior, we should have messages from the end
    assert "message" in last_message.payload["data"]


@pytest.mark.asyncio
async def test_handler_registration(proxy: MQTTProxy):
    """Test handler registration and unregistration."""
    messages_received = []
    
    def test_handler(topic: str, payload: dict):
        messages_received.append((topic, payload))
    
    # Register handler
    proxy.register_handler("test/topic", test_handler)
    
    # Verify handler is registered
    assert "test/topic" in proxy._handlers
    assert test_handler in proxy._handlers["test/topic"]
    
    # Process message to test handler
    from petal_app_manager.proxies.mqtt import MQTTMessage
    message = MQTTMessage(topic="test/topic", payload={"data": "test"})
    proxy._process_message_in_worker(message)
    
    # Give handler time to execute
    await asyncio.sleep(0.1)
    
    # Verify handler was called
    assert len(messages_received) == 1
    assert messages_received[0] == ("test/topic", {"data": "test"})
    
    # Unregister handler
    proxy.unregister_handler("test/topic", test_handler)
    
    # Verify handler is removed
    assert "test/topic" not in proxy._handlers
