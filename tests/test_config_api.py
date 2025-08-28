import pytest
import json
import tempfile
import yaml
import importlib.metadata as md
from pathlib import Path
from unittest.mock import patch, mock_open
from fastapi.testclient import TestClient

from src.petal_app_manager.api.config_api import router
from fastapi import FastAPI

# Create a test app with our config router
test_app = FastAPI()
test_app.include_router(router)

# Create test client
client = TestClient(test_app)

@pytest.fixture
def sample_config():
    return {
        "enabled_proxies": ["redis", "ext_mavlink", "db"],
        "enabled_petals": ["petal_warehouse", "mission_planner"],
        "petal_dependencies": {
            "petal_warehouse": ["redis", "ext_mavlink"],
            "flight_records": ["redis", "cloud"],
            "mission_planner": ["redis", "ext_mavlink"]
        }
    }

@pytest.fixture
def mock_config_file(sample_config):
    """Mock the config file reading/writing"""
    config_data = yaml.safe_dump(sample_config)
    
    def mock_file_operations(filename, mode='r', *args, **kwargs):
        if 'r' in mode:
            return mock_open(read_data=config_data)()
        elif 'w' in mode:
            # For write operations, we'll just return a mock that captures the data
            mock_file = mock_open()()
            return mock_file
    
    return mock_file_operations

def test_get_config_status(sample_config, mock_config_file):
    """Test getting the current configuration status"""
    
    with patch("builtins.open", mock_config_file):
        response = client.get("/api/petal-proxies-control/status")
    
    assert response.status_code == 200
    data = response.json()
    
    assert "enabled_proxies" in data
    assert "enabled_petals" in data
    assert "petal_dependencies" in data
    
    assert set(data["enabled_proxies"]) == set(sample_config["enabled_proxies"])
    assert set(data["enabled_petals"]) == set(sample_config["enabled_petals"])

def test_enable_petals_success(sample_config, mock_config_file):
    """Test successfully enabling petals with met dependencies"""
    
    with patch("builtins.open", mock_config_file):
        response = client.post("/api/petal-proxies-control/petals/control", json={
            "petals": ["flight_records"],
            "action": "ON"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is False  # Should fail because cloud proxy is not enabled
    assert "errors" in data
    assert any("missing dependencies" in error for error in data["errors"])

def test_enable_petals_missing_dependencies(sample_config, mock_config_file):
    """Test enabling petals with missing dependencies"""
    
    with patch("builtins.open", mock_config_file):
        response = client.post("/api/petal-proxies-control/petals/control", json={
            "petals": ["flight_records"],
            "action": "ON"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is False
    assert "errors" in data
    assert any("missing dependencies ['cloud']" in error for error in data["errors"])

def test_disable_petals_success(sample_config, mock_config_file):
    """Test successfully disabling petals"""
    
    with patch("builtins.open", mock_config_file):
        response = client.post("/api/petal-proxies-control/petals/control", json={
            "petals": ["petal_warehouse"],
            "action": "OFF"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert len(data["results"]) == 1
    assert "Disabled petal: petal_warehouse" in data["results"]

def test_enable_proxies_success(sample_config, mock_config_file):
    """Test successfully enabling proxies"""
    
    with patch("builtins.open", mock_config_file):
        response = client.post("/api/petal-proxies-control/proxies/control", json={
            "petals": ["cloud"],  # Using petals field for proxy names
            "action": "ON"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert len(data["results"]) == 1
    assert "Enabled proxy: cloud" in data["results"]

def test_disable_proxy_with_dependencies(sample_config, mock_config_file):
    """Test disabling a proxy that petals depend on"""
    
    with patch("builtins.open", mock_config_file):
        response = client.post("/api/petal-proxies-control/proxies/control", json={
            "petals": ["redis"],  # Redis is required by enabled petals
            "action": "OFF"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is False
    assert "errors" in data
    assert any("required by petals" in error for error in data["errors"])

def test_invalid_action():
    """Test using an invalid action"""
    
    response = client.post("/api/petal-proxies-control/petals/control", json={
        "petals": ["test_petal"],
        "action": "INVALID"
    })
    
    assert response.status_code == 400
    assert "Action must be either 'ON' or 'OFF'" in response.json()["detail"]

def test_empty_petals_list():
    """Test with empty petals list"""
    
    response = client.post("/api/petal-proxies-control/petals/control", json={
        "petals": [],
        "action": "ON"
    })
    
    assert response.status_code == 400
    assert "At least one petal name must be provided" in response.json()["detail"]

def test_batch_operations(sample_config, mock_config_file):
    """Test enabling/disabling multiple petals at once"""
    
    with patch("builtins.open", mock_config_file):
        # First enable cloud proxy
        response = client.post("/api/petal-proxies-control/proxies/control", json={
            "petals": ["cloud"],
            "action": "ON"
        })
        assert response.status_code == 200
        
        # Now try to enable multiple petals
        response = client.post("/api/petal-proxies-control/petals/control", json={
            "petals": ["petal_warehouse", "mission_planner"],
            "action": "ON"
        })
    
    assert response.status_code == 200
    data = response.json()
    
    # Both should succeed since their dependencies (redis, ext_mavlink) are enabled
    assert data["success"] is True
    assert len(data["results"]) == 0

def test_list_all_components(sample_config, mock_config_file):
    """Test the list all components endpoint"""
    
    # Update sample config to include proxy dependencies
    config_with_proxy_deps = sample_config.copy()
    config_with_proxy_deps["proxy_dependencies"] = {
        "db": ["cloud"],
        "bucket": ["cloud"]
    }
    
    def mock_file_operations(path, mode="r"):
        if "r" in mode:
            mock_file = mock_open(read_data=yaml.safe_dump(config_with_proxy_deps))()
            return mock_file
        else:
            mock_file = mock_open()()
            return mock_file
    
    # Mock entry points for petals
    class MockEntryPoint:
        def __init__(self, name):
            self.name = name
    
    mock_entry_points = [
        MockEntryPoint("petal_warehouse"),
        MockEntryPoint("flight_records"),
        MockEntryPoint("mission_planner")
    ]
    
    with patch("builtins.open", mock_file_operations), \
         patch("importlib.metadata.entry_points") as mock_ep:
        
        mock_ep.return_value = mock_entry_points
        
        response = client.get("/api/petal-proxies-control/components/list")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "petals" in data
    assert "proxies" in data
    assert "total_petals" in data
    assert "total_proxies" in data
    
    # Check petal information
    petal_names = [p["name"] for p in data["petals"]]
    assert "petal_warehouse" in petal_names
    assert "flight_records" in petal_names
    assert "mission_planner" in petal_names
    
    # Check that enabled status is correct
    petal_dict = {p["name"]: p for p in data["petals"]}
    assert petal_dict["petal_warehouse"]["enabled"] is True
    assert petal_dict["flight_records"]["enabled"] is False  # Not in enabled_petals
    
    # Check petal dependencies
    assert petal_dict["petal_warehouse"]["dependencies"] == ["redis", "ext_mavlink"]
    assert petal_dict["flight_records"]["dependencies"] == ["redis", "cloud"]
    
    # Check proxy information
    proxy_names = [p["name"] for p in data["proxies"]]
    expected_proxies = ["ext_mavlink", "redis", "db", "cloud", "bucket", "ftp_mavlink"]
    for expected in expected_proxies:
        assert expected in proxy_names
    
    # Check proxy enabled status
    proxy_dict = {p["name"]: p for p in data["proxies"]}
    assert proxy_dict["redis"]["enabled"] is True
    assert proxy_dict["ext_mavlink"]["enabled"] is True
    assert proxy_dict["db"]["enabled"] is True
    assert proxy_dict["cloud"]["enabled"] is False  # Not in enabled_proxies
    
    # Check proxy dependencies
    assert proxy_dict["db"]["dependencies"] == ["cloud"]
    assert proxy_dict["bucket"]["dependencies"] == ["cloud"]
    
    # Check dependents (what depends on each proxy)
    assert "petal:petal_warehouse" in proxy_dict["redis"]["dependents"]
    assert "petal:flight_records" in proxy_dict["cloud"]["dependents"]
    assert "proxy:db" in proxy_dict["cloud"]["dependents"]
    
    # Check totals
    assert data["total_petals"] == len(data["petals"])
    assert data["total_proxies"] == len(data["proxies"])
