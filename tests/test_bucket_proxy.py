import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json

from petal_app_manager.proxies.bucket import S3BucketProxy


class TestS3BucketProxy:
    """Test cases for S3BucketProxy."""
    
    def test_file_extension_validation(self):
        """Test file extension validation."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy
        )
        
        # Valid extensions
        assert proxy._validate_file_extension("test.ulg") is True
        assert proxy._validate_file_extension("test.bag") is True
        assert proxy._validate_file_extension("TEST.ULG") is True
        assert proxy._validate_file_extension("TEST.BAG") is True
        assert proxy._validate_file_extension("flight_log.ulg") is True
        assert proxy._validate_file_extension("sensor_data.bag") is True
        
        # Invalid extensions
        assert proxy._validate_file_extension("test.txt") is False
        assert proxy._validate_file_extension("test.log") is False
        assert proxy._validate_file_extension("test.mp4") is False
        assert proxy._validate_file_extension("test") is False
        assert proxy._validate_file_extension("") is False
        assert proxy._validate_file_extension(None) is False
    
    def test_file_content_validation(self):
        """Test file content validation."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy
        )
        
        # Define valid file headers
        ulog_header   = b"ULog\x01\x12\x35\x01\x00"          # 7‑byte magic + v1 + pad
        rosbag_header = b"#ROSBAG V2.0\n"                    # starts with '#ROSBAG'

        # Test valid ULog file
        with tempfile.NamedTemporaryFile(suffix='.ulg', delete=False) as f:
            f.write(ulog_header)
            ulg_path = Path(f.name)
        
        try:
            result = proxy._validate_file_content(ulg_path)
            assert result["valid"] is True
            assert result["extension"] == ".ulg"
            assert result["file_size"] > 0
        finally:
            ulg_path.unlink()
        
        # Test valid ROS bag file
        with tempfile.NamedTemporaryFile(suffix='.bag', delete=False) as f:
            f.write(rosbag_header)
            bag_path = Path(f.name)
        
        try:
            result = proxy._validate_file_content(bag_path)
            assert result["valid"] is True
            assert result["extension"] == ".bag"
            assert result["file_size"] > 0
        finally:
            bag_path.unlink()
        
        # Test invalid ULog file
        with tempfile.NamedTemporaryFile(suffix='.ulg', delete=False) as f:
            f.write(b'InvalidData')
            invalid_ulg_path = Path(f.name)
        
        try:
            result = proxy._validate_file_content(invalid_ulg_path)
            assert result["valid"] is False
            assert "Invalid ULog header" in result["error"]
        finally:
            invalid_ulg_path.unlink()
        
        # Test empty file
        with tempfile.NamedTemporaryFile(suffix='.ulg', delete=False) as f:
            empty_path = Path(f.name)
        
        try:
            result = proxy._validate_file_content(empty_path)
            assert result["valid"] is False
            assert "File is empty" in result["error"]
        finally:
            empty_path.unlink()
        
        # Test non-existent file
        non_existent = Path("/non/existent/file.ulg")
        result = proxy._validate_file_content(non_existent)
        assert result["valid"] is False
        assert "File does not exist" in result["error"]
    
    def test_s3_key_generation(self):
        """Test S3 key generation."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy,
            upload_prefix="flight_logs/"
        )
        
        machine_id = "test-machine-123"
        
        # Test normal filename
        key = proxy._generate_s3_key("flight_log.ulg", machine_id)
        assert key.startswith("test-machine-123/flight-logs/")
        assert key.endswith("_flight_log.ulg")
        
        # Test filename with path
        key = proxy._generate_s3_key("path/to/file.bag", machine_id)
        assert key.startswith("test-machine-123/flight-logs/")
        assert key.endswith("_file.bag")
        
        # Test uppercase extension
        key = proxy._generate_s3_key("TEST.ULG", machine_id)
        assert key.startswith("test-machine-123/flight-logs/")
        assert key.endswith("_TEST.ULG")
    
    def test_session_credentials_caching_structure(self):
        """Test session credentials caching structure."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy
        )
        
        # Test that cache structure is initialized
        assert hasattr(proxy, '_session_cache')
        assert 'credentials' in proxy._session_cache
        assert 'expires_at' in proxy._session_cache
        assert proxy._session_cache['credentials'] is None
        assert proxy._session_cache['expires_at'] == 0
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        # Valid configuration
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy
        )
        assert proxy.session_token_url == "http://test:3000/token"
        assert proxy.bucket_name == "test-bucket"
        assert proxy.upload_prefix == "flight_logs/"  # default with trailing slash
        
        # Custom configuration
        proxy = S3BucketProxy(
            session_token_url="https://auth.example.com/token",
            bucket_name="my-custom-bucket",
            local_db_proxy=mock_local_db_proxy,
            upload_prefix="logs",
            debug=True,
            request_timeout=60
        )
        assert proxy.session_token_url == "https://auth.example.com/token"
        assert proxy.bucket_name == "my-custom-bucket"
        assert proxy.upload_prefix == "logs/"  # adds trailing slash
        assert proxy.debug == True
        assert proxy.request_timeout == 60
        assert proxy.upload_prefix == "logs/"  # should add trailing slash
        assert proxy.debug is True
        assert proxy.request_timeout == 60
    
    @pytest.mark.asyncio
    async def test_start_validation(self):
        """Test proxy start validation."""
        # Create a mock LocalDBProxy
        mock_local_db_proxy = MagicMock()
        mock_local_db_proxy.machine_id = "test-machine-123"
        
        # Missing session_token_url should raise ValueError
        proxy = S3BucketProxy(
            session_token_url="",
            bucket_name="test-bucket",
            local_db_proxy=mock_local_db_proxy
        )
        
        with pytest.raises(ValueError, match="SESSION_TOKEN_URL and BUCKET_NAME must be configured"):
            await proxy.start()
        
        # Missing bucket_name should raise ValueError
        proxy = S3BucketProxy(
            session_token_url="http://test:3000/token",
            bucket_name="",
            local_db_proxy=mock_local_db_proxy
        )
        
        with pytest.raises(ValueError, match="SESSION_TOKEN_URL and BUCKET_NAME must be configured"):
            await proxy.start()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
