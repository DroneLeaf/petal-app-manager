#!/usr/bin/env python3
"""
Test the new list all components endpoint
"""

import yaml
import tempfile
from pathlib import Path
import sys
import os

# Add the src directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_list_components_endpoint():
    """Test the new list all components endpoint"""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from unittest.mock import patch, mock_open
    import importlib.metadata as md
    
    # Import our API
    from petal_app_manager.api.config_api import router
    
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    
    # Create test configuration
    test_config = {
        "enabled_proxies": ["ext_mavlink", "redis", "cloud"],
        "enabled_petals": ["petal_warehouse"],
        "petal_dependencies": {
            "petal_warehouse": ["redis", "ext_mavlink"],
            "flight_records": ["redis", "cloud"],
            "mission_planner": ["redis", "ext_mavlink"]
        },
        "proxy_dependencies": {
            "db": ["cloud"],
            "bucket": ["cloud"]
        }
    }
    
    def mock_file_operations(path, mode="r"):
        if "r" in mode:
            mock_file = mock_open(read_data=yaml.safe_dump(test_config))()
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
        MockEntryPoint("mission_planner"),
        MockEntryPoint("hello_world")  # Additional petal not in config
    ]
    
    with patch("builtins.open", mock_file_operations), \
         patch("importlib.metadata.entry_points") as mock_ep:
        
        mock_ep.return_value = mock_entry_points
        
        response = client.get("/api/petal-proxies-control/components/list")
    
    print("Response status:", response.status_code)
    
    if response.status_code == 200:
        data = response.json()
        
        print("✅ Endpoint successful!")
        print(f"Total petals: {data.get('total_petals')}")
        print(f"Total proxies: {data.get('total_proxies')}")
        
        print("\nPetals:")
        for petal in data.get('petals', []):
            status = "✅ ENABLED" if petal['enabled'] else "❌ DISABLED"
            deps = petal['dependencies'] if petal['dependencies'] else "None"
            print(f"  - {petal['name']}: {status}, Dependencies: {deps}")
        
        print("\nProxies:")
        for proxy in data.get('proxies', []):
            status = "✅ ENABLED" if proxy['enabled'] else "❌ DISABLED"
            deps = proxy['dependencies'] if proxy['dependencies'] else "None"
            dependents = proxy['dependents'] if proxy['dependents'] else "None"
            print(f"  - {proxy['name']}: {status}")
            print(f"    Dependencies: {deps}")
            print(f"    Dependents: {dependents}")
        
        # Verify response structure
        assert 'petals' in data
        assert 'proxies' in data
        assert 'total_petals' in data
        assert 'total_proxies' in data
        
        # Check that all known proxies are listed
        proxy_names = [p['name'] for p in data['proxies']]
        expected_proxies = ["ext_mavlink", "redis", "db", "cloud", "bucket", "ftp_mavlink"]
        for expected in expected_proxies:
            assert expected in proxy_names, f"Missing expected proxy: {expected}"
        
        # Check that petals have correct enabled status
        petal_dict = {p['name']: p for p in data['petals']}
        assert petal_dict['petal_warehouse']['enabled'] == True
        assert petal_dict['flight_records']['enabled'] == False
        
        # Check proxy enabled status
        proxy_dict = {p['name']: p for p in data['proxies']}
        assert proxy_dict['redis']['enabled'] == True
        assert proxy_dict['db']['enabled'] == False  # Not in enabled_proxies
        
        # Check dependencies
        assert proxy_dict['db']['dependencies'] == ['cloud']
        assert proxy_dict['bucket']['dependencies'] == ['cloud']
        
        print("\n✅ All validation checks passed!")
        
    else:
        print(f"❌ Endpoint failed with status {response.status_code}")
        print("Response:", response.text)

if __name__ == "__main__":
    test_list_components_endpoint()
