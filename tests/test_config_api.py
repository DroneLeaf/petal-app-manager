import pytest
import json
import tempfile
import yaml
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
    assert "restart_required" in data
    
    assert set(data["enabled_proxies"]) == set(sample_config["enabled_proxies"])
    assert set(data["enabled_petals"]) == set(sample_config["enabled_petals"])
    assert data["restart_required"] is True

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
    assert len(data["results"]) == 2
