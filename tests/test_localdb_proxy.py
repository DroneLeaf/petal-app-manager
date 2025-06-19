import pytest
import pytest_asyncio
import asyncio
import http.client
import json
import logging
import platform
import subprocess
import concurrent.futures
from unittest.mock import patch, MagicMock, PropertyMock
from petal_app_manager.proxies.localdb import LocalDBProxy
import uuid

from typing import Generator, AsyncGenerator

@pytest_asyncio.fixture
async def proxy() -> AsyncGenerator[LocalDBProxy, None]:
    """Create a LocalDBProxy instance for testing."""
    proxy = LocalDBProxy(host="localhost", port=3000, debug=True)
    
    # Mock the machine ID retrieval to avoid actual system calls
    with patch.object(proxy, '_get_machine_id', return_value="test-machine-id"):
        await proxy.start()
        yield proxy  # This is what gets passed to the test
        await proxy.stop()

def test_get_machine_id():
    """Test that _get_machine_id returns a string or specifically a UUID4."""
    proxy = LocalDBProxy(host="localhost", port=3000)
    
    # Call the private method directly
    machine_id = proxy._get_machine_id()
    
    if machine_id is not None:
        assert isinstance(machine_id, str)
        assert len(machine_id) > 0, "Machine ID should be a non-empty string"
        
        # Try to validate if it's a UUID4
        try:
            uuid_obj = uuid.UUID(machine_id)
            assert uuid_obj.version == 4, f"Expected UUID4, got UUID{uuid_obj.version}"
        except ValueError:
            # If not a valid UUID format, still pass as we only require a string
            pass
    else:
        raise AssertionError("Machine ID should not be None, unless running in an environment without the executable.")

@pytest.mark.asyncio
async def test_get_current_instance_with_mock():
    """Test _get_current_instance method with mocking."""
    proxy = LocalDBProxy(host="localhost", port=3000)
    proxy._machine_id = "test-machine-id"
    
    # Mock successful response
    mock_response = {"id": "test-machine-id", "name": "Test Robot", "status": "active"}
    
    with patch.object(proxy, 'get_item', return_value=mock_response):
        result = await proxy._get_current_instance()
        assert result == mock_response
        proxy.get_item.assert_called_once_with(
            table_name="config-robot_instances",
            partition_key="id",
            partition_value="test-machine-id"
        )
    
    # Test when machine ID is not available
    proxy._machine_id = None
    result = await proxy._get_current_instance()
    assert result is None
    
    # Test when exception occurs
    proxy._machine_id = "test-machine-id"
    with patch.object(proxy, 'get_item', side_effect=Exception("Test error")):
        result = await proxy._get_current_instance()
        assert result is None

@pytest.mark.asyncio
@pytest.mark.hardware
async def test_get_current_instance_without_mock():
    """Test _get_current_instance method without mocking (integration test)."""
    # Create a real proxy instance
    proxy = LocalDBProxy(host="localhost", port=3000, debug=True)
    
    # Start the proxy to get a machine ID
    await proxy.start()
    
    try:
        # Only proceed with the test if we successfully got a machine ID
        if proxy._machine_id:
            # Call the method directly
            result = await proxy._get_current_instance()
            
            # We may or may not get actual data depending on if this robot
            # is registered in the database, but the method should not raise exceptions
            if result is not None:
                assert "data" in result
                assert isinstance(result["data"], dict)
                assert "id" in result["data"]
                assert result["data"]["id"] == proxy._machine_id
        else:
            # If we didn't get a machine ID, the method should return {"error": "Machine ID not available"}
            result = await proxy._get_current_instance()
            assert "error" in result
            
    finally:
        # Always clean up
        await proxy.stop()

@pytest.mark.asyncio
async def test_get_item(proxy: LocalDBProxy):
    """Test retrieving an item from the database."""
    mock_response = {"id": "123", "name": "Test Item", "status": "active"}
    
    # Mock the _remote_file_request method
    with patch.object(proxy, '_remote_file_request', return_value=mock_response):
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert result == mock_response
        proxy._remote_file_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-id",
                "table_name": "test-table",
                "partition_key": "id",
                "partition_value": "123"
            },
            '/drone/onBoard/config/getData',
            'POST'
        )

@pytest.mark.asyncio
async def test_scan_items_without_filters(proxy: LocalDBProxy):
    """Test scanning items without filters."""
    mock_response = [
        {"id": "123", "name": "Item 1"},
        {"id": "456", "name": "Item 2"}
    ]
    
    with patch.object(proxy, '_remote_file_request', return_value=mock_response):
        result = await proxy.scan_items(table_name="test-table")
        
        assert result == mock_response
        proxy._remote_file_request.assert_called_once_with(
            {
                "table_name": "test-table",
                "onBoardId": "test-machine-id"
            },
            '/drone/onBoard/config/scanData',
            'POST'
        )

@pytest.mark.asyncio
async def test_scan_items_with_filters(proxy: LocalDBProxy):
    """Test scanning items with filters."""
    mock_response = [{"id": "123", "name": "Item 1"}]
    filters = [{"filter_key_name": "organization_id", "filter_key_value": "org-123"}]
    
    with patch.object(proxy, '_remote_file_request', return_value=mock_response):
        result = await proxy.scan_items(table_name="test-table", filters=filters)
        
        assert result == mock_response
        proxy._remote_file_request.assert_called_once_with(
            {
                "table_name": "test-table",
                "onBoardId": "test-machine-id",
                "scanFilter": filters
            },
            '/drone/onBoard/config/scanData',
            'POST'
        )

@pytest.mark.asyncio
async def test_update_item(proxy: LocalDBProxy):
    """Test updating an item in the database."""
    mock_response = {"success": True}
    item_data = {"id": "123", "name": "Updated Item", "status": "inactive"}
    
    with patch.object(proxy, '_remote_file_request', return_value=mock_response):
        result = await proxy.update_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123",
            data=item_data
        )
        
        assert result == mock_response
        proxy._remote_file_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-id",
                "table_name": "test-table",
                "filter_key": "id",
                "filter_value": "123",
                "data": item_data
            },
            '/drone/onBoard/config/updateData',
            'POST'
        )

@pytest.mark.asyncio
async def test_delete_item(proxy: LocalDBProxy):
    """Test deleting an item from the database."""
    mock_response = {"success": True}
    
    with patch.object(proxy, '_remote_file_request', return_value=mock_response):
        result = await proxy.delete_item(
            table_name="test-table",
            filter_key="id",
            filter_value="123"
        )
        
        assert result == mock_response
        proxy._remote_file_request.assert_called_once_with(
            {
                "onBoardId": "test-machine-id",
                "table_name": "test-table",
                "filter_key": "id",
                "filter_value": "123"
            },
            '/drone/onBoard/config/deleteData',
            'POST'
        )

@pytest.mark.asyncio
async def test_no_machine_id():
    """Test behavior when machine ID is not available."""
    proxy = LocalDBProxy(host="localhost", port=3000)
    
    # Option 2: Use PropertyMock if you prefer patching
    with patch.object(LocalDBProxy, 'machine_id', new_callable=PropertyMock, return_value=None):
    
        await proxy.start()
        # Directly set the underlying attribute
        proxy._machine_id = None
        
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert "error" in result
        assert result["error"] == "Machine ID not available"
        
        await proxy.stop()