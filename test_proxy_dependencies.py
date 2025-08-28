#!/usr/bin/env python3
"""
Test script to verify proxy dependency functionality works correctly.
"""

import yaml
import tempfile
from pathlib import Path
import os

def create_test_config():
    """Create a test configuration with proxy dependencies"""
    return {
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

def check_proxy_dependencies(config, proxy_to_disable):
    """Check if a proxy can be disabled based on dependencies"""
    enabled_proxies = set(config.get("enabled_proxies", []))
    proxy_dependencies = config.get("proxy_dependencies", {})
    
    # Check if any enabled proxies depend on this proxy
    dependent_proxies = []
    for proxy, deps in proxy_dependencies.items():
        if proxy in enabled_proxies and proxy_to_disable in deps:
            dependent_proxies.append(proxy)
    
    return dependent_proxies

def check_proxy_can_enable(config, proxy_to_enable):
    """Check if a proxy can be enabled based on its dependencies"""
    enabled_proxies = set(config.get("enabled_proxies", []))
    proxy_dependencies = config.get("proxy_dependencies", {})
    
    required_deps = proxy_dependencies.get(proxy_to_enable, [])
    missing_deps = [dep for dep in required_deps if dep not in enabled_proxies]
    
    return missing_deps

def test_proxy_dependencies():
    """Test proxy dependency validation"""
    print("Testing Proxy Dependencies...")
    print("=" * 50)
    
    # Create test configuration
    config = create_test_config()
    
    # Test 1: Try to disable cloud while db and bucket are enabled (should fail)
    print("Test 1: Try to disable 'cloud' while 'db' and 'bucket' depend on it")
    print("-" * 60)
    
    dependent_proxies = check_proxy_dependencies(config, "cloud")
    
    if dependent_proxies:
        print(f"✅ PASS: Found dependent proxies: {dependent_proxies}")
        print(f"   Cannot disable 'cloud' because it's required by: {dependent_proxies}")
    else:
        print("❌ FAIL: No dependent proxies found")
    
    print()
    
    # Test 2: Disable db and bucket first, then cloud (should succeed)
    print("Test 2: Disable 'db' and 'bucket' first, then 'cloud'")
    print("-" * 60)
    
    # Remove db and bucket from enabled proxies
    config_modified = config.copy()
    config_modified["enabled_proxies"] = [p for p in config_modified["enabled_proxies"] if p not in ["db", "bucket"]]
    
    dependent_proxies = check_proxy_dependencies(config_modified, "cloud")
    
    if not dependent_proxies:
        print("✅ PASS: No dependent proxies found, 'cloud' can now be disabled")
    else:
        print(f"❌ FAIL: Still found dependent proxies: {dependent_proxies}")
    
    print()
    
    # Test 3: Try to enable db without cloud (should fail)
    print("Test 3: Try to enable 'db' without 'cloud' being enabled")
    print("-" * 60)
    
    # Remove cloud from enabled proxies
    config_no_cloud = config.copy()
    config_no_cloud["enabled_proxies"] = [p for p in config_no_cloud["enabled_proxies"] if p != "cloud"]
    
    missing_deps = check_proxy_can_enable(config_no_cloud, "db")
    
    if missing_deps:
        print(f"✅ PASS: Cannot enable 'db' - missing dependencies: {missing_deps}")
    else:
        print("❌ FAIL: 'db' should not be able to be enabled without 'cloud'")
    
    print()
    
    # Test 4: Try to enable bucket without cloud (should fail)
    print("Test 4: Try to enable 'bucket' without 'cloud' being enabled")
    print("-" * 60)
    
    missing_deps = check_proxy_can_enable(config_no_cloud, "bucket")
    
    if missing_deps:
        print(f"✅ PASS: Cannot enable 'bucket' - missing dependencies: {missing_deps}")
    else:
        print("❌ FAIL: 'bucket' should not be able to be enabled without 'cloud'")
    
    print()
    
    # Test 5: Enable cloud first, then db and bucket (should succeed)
    print("Test 5: Enable 'cloud' first, then 'db' and 'bucket'")
    print("-" * 60)
    
    # Start with minimal config
    minimal_config = {
        "enabled_proxies": ["ext_mavlink", "redis", "cloud"],
        "enabled_petals": [],
        "proxy_dependencies": {
            "db": ["cloud"],
            "bucket": ["cloud"]
        }
    }
    
    # Try to enable db with cloud present
    missing_deps_db = check_proxy_can_enable(minimal_config, "db")
    missing_deps_bucket = check_proxy_can_enable(minimal_config, "bucket")
    
    if not missing_deps_db and not missing_deps_bucket:
        print("✅ PASS: Both 'db' and 'bucket' can be enabled when 'cloud' is present")
    else:
        print(f"❌ FAIL: Missing deps for db: {missing_deps_db}, bucket: {missing_deps_bucket}")
    
    print()
    print("All tests completed!")
    print()
    print("Summary:")
    print("- Proxy dependencies prevent disabling a proxy that others depend on")
    print("- Proxy dependencies prevent enabling a proxy without its dependencies")
    print("- This ensures configuration consistency and prevents runtime errors")

if __name__ == "__main__":
    test_proxy_dependencies()
