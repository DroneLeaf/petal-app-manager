import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch, mock_open
import yaml
from pathlib import Path
import sys

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from petal_app_manager.api.config_api import router

from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)

class TestProxyDependencies(unittest.TestCase):
    
    def setUp(self):
        """Set up test configuration with proxy dependencies"""
        self.sample_config = {
            "enabled_proxies": ["ext_mavlink", "db", "redis", "bucket", "ftp_mavlink", "cloud"],
            "enabled_petals": ["petal_warehouse", "mission_planner"],
            "petal_dependencies": {
                "flight_records": ["redis", "cloud"],
                "mission_planner": ["redis", "ext_mavlink"],
                "petal_warehouse": ["redis", "ext_mavlink"]
            },
            "proxy_dependencies": {
                "db": ["cloud"],
                "bucket": ["cloud"]
            }
        }
    
    def create_mock_file(self, config):
        """Create a mock file that returns the config and can be written to"""
        def mock_file_operations(path, mode="r"):
            if "r" in mode:
                mock_file = mock_open(read_data=yaml.safe_dump(config))()
                return mock_file
            else:
                # For write operations, we'll just return a mock that captures the data
                mock_file = mock_open()()
                return mock_file
        
        return mock_file_operations
    
    def test_cannot_disable_cloud_with_dependent_proxies(self):
        """Test that cloud cannot be disabled while db and bucket depend on it"""
        
        mock_config_file = self.create_mock_file(self.sample_config)
        
        with patch("builtins.open", mock_config_file):
            response = client.post("/api/petal-proxies-control/proxies/control", json={
                "petals": ["cloud"],  # Using petals field for proxy names
                "action": "OFF"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should fail because db and bucket depend on cloud
        assert data["success"] is False
        assert "errors" in data
        assert any("required by proxies ['db', 'bucket']" in error or "required by proxies ['bucket', 'db']" in error for error in data["errors"])
    
    def test_cannot_enable_db_without_cloud(self):
        """Test that db cannot be enabled without cloud being enabled"""
        
        # Create config without cloud
        config_without_cloud = self.sample_config.copy()
        config_without_cloud["enabled_proxies"] = ["ext_mavlink", "redis", "ftp_mavlink"]
        
        mock_config_file = self.create_mock_file(config_without_cloud)
        
        with patch("builtins.open", mock_config_file):
            response = client.post("/api/petal-proxies-control/proxies/control", json={
                "petals": ["db"],  # Using petals field for proxy names
                "action": "ON"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should fail because db depends on cloud
        assert data["success"] is False
        assert "errors" in data
        assert any("missing proxy dependencies ['cloud']" in error for error in data["errors"])
    
    def test_can_disable_cloud_after_disabling_dependents(self):
        """Test that cloud can be disabled after disabling db and bucket"""
        
        # Create config without db and bucket
        config_without_dependents = self.sample_config.copy()
        config_without_dependents["enabled_proxies"] = ["ext_mavlink", "redis", "ftp_mavlink", "cloud"]
        
        mock_config_file = self.create_mock_file(config_without_dependents)
        
        with patch("builtins.open", mock_config_file):
            response = client.post("/api/petal-proxies-control/proxies/control", json={
                "petals": ["cloud"],  # Using petals field for proxy names
                "action": "OFF"
            })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should succeed because no proxies depend on cloud anymore
        assert data["success"] is True
        assert len(data["results"]) == 1
        assert "Disabled proxy: cloud" in data["results"]
    
    def test_proxy_dependencies_in_status(self):
        """Test that proxy dependencies are included in the status response"""
        
        mock_config_file = self.create_mock_file(self.sample_config)
        
        with patch("builtins.open", mock_config_file):
            response = client.get("/api/petal-proxies-control/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "proxy_dependencies" in data
        assert data["proxy_dependencies"] == {
            "db": ["cloud"],
            "bucket": ["cloud"]
        }

if __name__ == "__main__":
    unittest.main()
