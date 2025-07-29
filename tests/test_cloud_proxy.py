import pytest
import pytest_asyncio
import asyncio
import http.client
import json
import logging
import time
from unittest.mock import patch, MagicMock, Mock
from petal_app_manager.proxies.cloud import CloudDBProxy
from petal_app_manager import Config

from typing import Generator, AsyncGenerator

@pytest_asyncio.fixture
async def proxy() -> AsyncGenerator[CloudDBProxy, None]:
    """Create a CloudDBProxy instance for testing."""
    mock_local_db_proxy = MagicMock()
    mock_local_db_proxy.machine_id = "test-machine-123"

    proxy = CloudDBProxy(
        access_token_url="https://example.com/token",
        endpoint="https://api.example.com",
        local_db_proxy=mock_local_db_proxy,
        debug=True
    )
    
    # Mock the credentials to avoid actual network calls
    mock_credentials = {"accessToken": "test-token-123"}
    proxy._session_cache = {
        'credentials': mock_credentials,
        'expires_at': time.time() + 3600  # Valid for 1 hour
    }
    
    await proxy.start()
    yield proxy
    await proxy.stop()

@pytest.mark.asyncio
async def test_get_access_token_caching():
    """Test that access tokens are properly cached."""
    mock_local_db_proxy = MagicMock()
    mock_local_db_proxy.machine_id = "test-machine-123"

    proxy = CloudDBProxy(
        access_token_url="https://example.com/token",
        endpoint="https://api.example.com",
        local_db_proxy=mock_local_db_proxy,
        debug=True
    )
    
    mock_credentials = {"accessToken": "test-token-456"}
    current_time = time.time()
    
    # Mock the token fetch to avoid network calls
    with patch.object(proxy, '_get_access_token', return_value=mock_credentials):
        await proxy.start()
    
    # Set cached credentials
    proxy._session_cache = {
        'credentials': mock_credentials,
        'expires_at': current_time + 3600
    }
    
    # Should return cached credentials without making a request
    result = await proxy._get_access_token()
    assert result == mock_credentials
    
    await proxy.stop()

@pytest.mark.asyncio
async def test_get_access_token_expired():
    """Test token refresh when cached token is expired."""
    mock_local_db_proxy = MagicMock()
    mock_local_db_proxy.machine_id = "test-machine-123"

    proxy = CloudDBProxy(
        access_token_url="https://example.com/token",
        endpoint="https://api.example.com",
        local_db_proxy=mock_local_db_proxy,
        debug=True
    )
    
    old_credentials = {"accessToken": "old-token"}
    new_credentials = {"accessToken": "new-token"}
    
    # Mock the initial start to avoid network calls
    with patch.object(proxy, '_get_access_token', return_value=old_credentials):
        await proxy.start()
    
    # Set expired credentials
    proxy._session_cache = {
        'credentials': old_credentials,
        'expires_at': time.time() - 1  # Expired
    }
    
    # Create an async mock that returns new credentials
    async def mock_executor(executor, func):
        return new_credentials
    
    with patch.object(proxy._loop, 'run_in_executor', side_effect=mock_executor):
        result = await proxy._get_access_token()
        assert result == new_credentials
    
    await proxy.stop()

@pytest.mark.asyncio
async def test_get_item(proxy: CloudDBProxy):
    """Test retrieving an item from the cloud database."""
    mock_response = {"data": {"id": "123", "name": "Test Item", "status": "active", "robot_instance_id": "test-machine-123"}, "success": True}
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert result == mock_response
        proxy._cloud_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-123",
                "table_name": "test-table",
                "partition_key": "id",
                "partition_value": "123"
            },
            proxy.get_data_url,
            'POST'
        )

@pytest.mark.asyncio
async def test_get_item_soft_deleted(proxy: CloudDBProxy):
    """Test that soft-deleted items are filtered out."""
    mock_response = {"data": {"id": "123", "name": "Test Item", "deleted": True, "robot_instance_id": "test-machine-123"}, "success": True}
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert "error" in result
        assert result["error"] == "Item not found or has been deleted"

@pytest.mark.asyncio
async def test_get_item_wrong_robot_id(proxy: CloudDBProxy):
    """Test that items belonging to different machines are filtered out."""
    mock_response = {"data": {"id": "123", "name": "Test Item", "robot_instance_id": "different-machine-id"}, "success": True}
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert "error" in result
        assert result["error"] == "Item not found or access denied"

@pytest.mark.asyncio
async def test_scan_items_without_filters(proxy: CloudDBProxy):
    """Test scanning items without filters."""
    mock_response = {
        "data": [
            {"id": "123", "name": "Item 1", "robot_instance_id": "test-machine-123"},
            {"id": "456", "name": "Item 2", "robot_instance_id": "test-machine-123"}
        ],
        "success": True
    }
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.scan_items(
            table_name="test-table"
        )
        
        assert result == mock_response
        proxy._cloud_request.assert_called_once_with(
            {
                "table_name": "test-table",
                "onBoardId": "test-machine-123",
                "scanFilter": [{"filter_key_name": "robot_instance_id", "filter_key_value": "test-machine-123"}]
            },
            proxy.scan_data_url,
            'POST'
        )

@pytest.mark.asyncio
async def test_scan_items_filters_soft_deleted(proxy: CloudDBProxy):
    """Test that soft-deleted items are filtered out from scan results."""
    mock_response = {
        "data": [
            {"id": "123", "name": "Item 1", "robot_instance_id": "test-machine-123"},
            {"id": "456", "name": "Item 2", "deleted": True, "robot_instance_id": "test-machine-123"},
            {"id": "789", "name": "Item 3", "robot_instance_id": "test-machine-123"}
        ],
        "success": True
    }
    
    expected_filtered = {
        "data": [
            {"id": "123", "name": "Item 1", "robot_instance_id": "test-machine-123"},
            {"id": "789", "name": "Item 3", "robot_instance_id": "test-machine-123"}
        ],
        "success": True
    }
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.scan_items(
            table_name="test-table"
        )
        
        assert result == expected_filtered

@pytest.mark.asyncio
async def test_scan_items_with_filters(proxy: CloudDBProxy):
    """Test scanning items with filters."""
    mock_response = {
        "data": [{"id": "123", "name": "Item 1", "robot_instance_id": "test-machine-123"}],
        "success": True
    }
    filters = [{"filter_key_name": "organization_id", "filter_key_value": "org-123"}]
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.scan_items(
            table_name="test-table",
            filters=filters
        )
        
        assert result == mock_response
        proxy._cloud_request.assert_called_once_with(
            {
                "table_name": "test-table",
                "onBoardId": "test-machine-123",
                "scanFilter": filters + [{"filter_key_name": "robot_instance_id", "filter_key_value": "test-machine-123"}]
            },
            proxy.scan_data_url,
            'POST'
        )

@pytest.mark.asyncio
async def test_update_item(proxy: CloudDBProxy):
    """Test updating an item in the cloud database."""
    mock_response = {"success": True}
    item_data = {"id": "123", "name": "Updated Item", "status": "inactive"}
    expected_data = item_data.copy()
    expected_data["robot_instance_id"] = "test-machine-123"
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.update_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123",
            data=item_data
        )
        
        assert result == mock_response
        proxy._cloud_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-123",
                "table_name": "test-table",
                "filter_key": "id",
                "filter_value": "123",
                "data": expected_data
            },
            proxy.update_data_url,
            'POST'
        )

@pytest.mark.asyncio
async def test_set_item(proxy: CloudDBProxy):
    """Test setting an item in the cloud database."""
    mock_response = {"success": True}
    item_data = {"id": "123", "name": "New Item", "status": "active"}
    expected_data = item_data.copy()
    expected_data["robot_instance_id"] = "test-machine-123"
    
    with patch.object(proxy, '_cloud_request', return_value=mock_response):
        result = await proxy.set_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123",
            data=item_data
        )
        
        assert result == mock_response
        proxy._cloud_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-123",
                "table_name": "test-table",
                "filter_key": "id",
                "filter_value": "123",
                "data": expected_data
            },
            proxy.set_data_url,
            'POST'
        )

@pytest.mark.asyncio
async def test_delete_item(proxy: CloudDBProxy):
    """Test soft deleting an item from the cloud database."""
    # Mock the existing item retrieval (direct database call)
    existing_item = {"id": "123", "name": "Test Item", "status": "active"}
    mock_get_response = {"data": existing_item, "success": True}
    
    # Mock the update response
    mock_update_response = {"success": True}
    
    with patch.object(proxy, '_cloud_request', return_value=mock_get_response), \
         patch.object(proxy, 'update_item', return_value=mock_update_response):
        
        result = await proxy.delete_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123"
        )
        
        assert result == mock_update_response
        
        # Verify _cloud_request was called for direct database access
        proxy._cloud_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-123",
                "table_name": "test-table",
                "partition_key": "id",
                "partition_value": "123"
            },
            proxy.get_data_url,
            'POST'
        )
        
        # Verify update_item was called with deleted=True
        expected_data = existing_item.copy()
        expected_data["deleted"] = True
        proxy.update_item.assert_called_once_with(
            table_name="test-table",
            filter_key="id",
            filter_value="123",
            data=expected_data
        )

@pytest.mark.asyncio
async def test_delete_item_not_found(proxy: CloudDBProxy):
    """Test deleting an item that doesn't exist."""
    mock_get_response = {"error": "Item not found", "success": False}
    
    with patch.object(proxy, '_cloud_request', return_value=mock_get_response):
        result = await proxy.delete_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123"
        )
        
        assert "error" in result
        assert result["error"] == "Item not found"

@pytest.mark.asyncio
async def test_authentication_failure():
    """Test behavior when authentication fails."""
    mock_local_db_proxy = MagicMock()
    mock_local_db_proxy.machine_id = "test-machine-123"

    proxy = CloudDBProxy(
        access_token_url="https://example.com/token",
        endpoint="https://api.example.com",
        local_db_proxy=mock_local_db_proxy,
        debug=True
    )
    
    # Mock the initial start to succeed, then test auth failure later
    with patch.object(proxy, '_get_access_token', return_value={"accessToken": "test"}):
        await proxy.start()
    
    # Now test authentication failure in a subsequent call
    with patch.object(proxy, '_get_access_token', side_effect=Exception("Auth failed")):
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert "error" in result
        assert "Authentication failed" in result["error"]
        
    await proxy.stop()

@pytest.mark.asyncio
async def test_configuration_validation():
    """Test that proper configuration is required."""
    
    # Test missing ACCESS_TOKEN_URL
    proxy1 = CloudDBProxy(
        access_token_url="",
        endpoint="https://api.example.com",
        local_db_proxy=MagicMock()
    )
    
    with pytest.raises(ValueError, match="ACCESS_TOKEN_URL and CLOUD_ENDPOINT must be configured"):
        await proxy1.start()
    
    # Test missing CLOUD_ENDPOINT
    proxy2 = CloudDBProxy(
        access_token_url="https://example.com/token",
        endpoint="",
        local_db_proxy=MagicMock()
    )
    
    with pytest.raises(ValueError, match="ACCESS_TOKEN_URL and CLOUD_ENDPOINT must be configured"):
        await proxy2.start()
