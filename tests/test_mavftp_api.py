"""
Tests for the MAVLink FTP API endpoints.
"""

import pytest
import logging
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from petal_app_manager.api.mavftp_api import router, _set_logger, ClearFailLogsRequest
from petal_app_manager.proxies.external import MavLinkFTPProxy


@pytest.fixture
def mock_logger():
    """Create a real logger for testing."""
    logger = logging.getLogger("test_mavftp_api")
    logger.handlers = [logging.StreamHandler()]
    logger.setLevel(logging.INFO)
    return logger


@pytest.fixture
def app(mock_logger):
    """Create a FastAPI app with the mavftp router for testing."""
    app = FastAPI()
    app.include_router(router)
    _set_logger(mock_logger)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_mavftp_proxy():
    """Create a mock MAVLink FTP proxy."""
    proxy = MagicMock(spec=MavLinkFTPProxy)
    proxy.clear_error_logs = AsyncMock()
    return proxy


@pytest.fixture
def mock_proxies(mock_mavftp_proxy):
    """Create mock proxies dictionary."""
    return {
        "mavftp": mock_mavftp_proxy
    }


class TestClearFailLogs:
    """Test cases for the clear_fail_logs endpoint."""
    
    @patch('petal_app_manager.api.mavftp_api.get_proxies')
    def test_clear_fail_logs_success(self, mock_get_proxies, client, mock_proxies):
        """Test successful clearing of fail logs."""
        mock_get_proxies.return_value = mock_proxies
        
        response = client.post(
            "/clear-error-logs",
            json={"remote_path": "fs/microsd"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Error logs cleared successfully"
        assert data["remote_path"] == "fs/microsd"
        
        # Verify the proxy method was called
        mock_proxies["mavftp"].clear_error_logs.assert_called_once_with("fs/microsd")
    
    @patch('petal_app_manager.api.mavftp_api.get_proxies')
    def test_clear_fail_logs_default_path(self, mock_get_proxies, client, mock_proxies):
        """Test clearing fail logs with default remote path."""
        mock_get_proxies.return_value = mock_proxies
        
        response = client.post(
            "/clear-error-logs",
            json={}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["remote_path"] == "fs/microsd"  # Default value
        
        # Verify the proxy method was called with default path
        mock_proxies["mavftp"].clear_error_logs.assert_called_once_with("fs/microsd")
    
    @patch('petal_app_manager.api.mavftp_api.get_proxies')
    def test_clear_fail_logs_no_mavftp_proxy(self, mock_get_proxies, client):
        """Test error when MAVLink FTP proxy is not available."""
        mock_get_proxies.return_value = {}  # No mavftp proxy
        
        response = client.post(
            "/clear-error-logs",
            json={"remote_path": "fs/microsd"}
        )
        
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert data["success"] is False
        assert "MAVLink FTP proxy not configured" in data["error"]
        assert "Cannot clear error logs" in data["message"]
    
    @patch('petal_app_manager.api.mavftp_api.get_proxies')
    def test_clear_fail_logs_proxy_exception(self, mock_get_proxies, client, mock_proxies):
        """Test handling of exceptions from the proxy."""
        mock_get_proxies.return_value = mock_proxies
        mock_proxies["mavftp"].clear_error_logs.side_effect = RuntimeError("Connection failed")
        
        response = client.post(
            "/clear-error-logs",
            json={"remote_path": "fs/microsd"}
        )
        
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert data["success"] is False
        assert "Connection failed" in data["error"]
        assert "Failed to clear error logs" in data["message"]
    
    @patch('petal_app_manager.api.mavftp_api.get_proxies')
    def test_clear_fail_logs_custom_path(self, mock_get_proxies, client, mock_proxies):
        """Test clearing fail logs with custom remote path."""
        mock_get_proxies.return_value = mock_proxies
        
        response = client.post(
            "/clear-error-logs",
            json={"remote_path": "fs/microsd/custom"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["remote_path"] == "fs/microsd/custom"
        
        # Verify the proxy method was called with custom path
        mock_proxies["mavftp"].clear_error_logs.assert_called_once_with("fs/microsd/custom")


class TestClearFailLogsRequest:
    """Test the request model validation."""
    
    def test_default_remote_path(self):
        """Test that the default remote path is set correctly."""
        request = ClearFailLogsRequest()
        assert request.remote_path == "fs/microsd"
    
    def test_custom_remote_path(self):
        """Test setting a custom remote path."""
        request = ClearFailLogsRequest(remote_path="fs/microsd/logs")
        assert request.remote_path == "fs/microsd/logs"
