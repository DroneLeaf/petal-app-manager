import pytest
import pytest_asyncio
import asyncio
import http.client
import json
import logging
import platform
import subprocess
import concurrent.futures
from unittest.mock import patch, MagicMock
from petal_app_manager.proxies.localdb import LocalDBProxy

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
    
    with patch.object(proxy, '_get_machine_id', return_value=None):
        await proxy.start()
        
        result = await proxy.get_item(
            table_name="test-table",
            partition_key="id",
            partition_value="123"
        )
        
        assert "error" in result
        assert result["error"] == "Machine ID not available"
        
        await proxy.stop()