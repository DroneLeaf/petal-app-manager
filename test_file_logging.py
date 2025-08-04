#!/usr/bin/env python3
"""
Test script to verify that Redis and MAVLink logging only goes to files.
This script will run for 30 seconds to test the logging behavior.
"""

import asyncio
import time
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from petal_app_manager.proxies.redis import RedisProxy
from petal_app_manager.proxies.external import MavLinkExternalProxy

async def test_redis_logging():
    """Test Redis proxy logging"""
    print("🔧 Testing Redis proxy logging...")
    
    # Initialize Redis proxy
    redis_proxy = RedisProxy(
        host="localhost",
        port=6379,
        db=0,
        unix_socket_path="/var/run/redis/redis-server.sock"  # Try socket first
    )
    
    try:
        await redis_proxy.start()
        
        # Test some operations that should log to file
        await redis_proxy.set("test_key", "test_value", ex=30)
        result = await redis_proxy.get("test_key")
        await redis_proxy.delete("test_key")
        
        # Test publish (this should log to file)
        redis_proxy.publish("test_channel", "test_message")
        
        print("✅ Redis operations completed - check app-redisproxy.log for entries")
        
    except Exception as e:
        print(f"❌ Redis test failed: {e}")
    finally:
        await redis_proxy.stop()

def test_mavlink_logging():
    """Test MAVLink proxy logging"""
    print("🔧 Testing MAVLink proxy logging...")
    
    try:
        # Initialize MAVLink proxy (this will log connection attempts)
        mavlink_proxy = MavLinkExternalProxy(
            endpoint="udp:127.0.0.1:14550",
            baud=57600,
            maxlen=1000
        )
        
        print("✅ MAVLink proxy initialized - check app-mavlinkexternalproxy.log for entries")
        
    except Exception as e:
        print(f"❌ MAVLink test failed: {e}")

async def main():
    """Main test function"""
    print("🚀 Starting file-only logging test...")
    print("📁 Log files will be created in the current directory:")
    print("   - app-redisproxy.log")
    print("   - app-mavlinkexternalproxy.log")
    print("🔍 Watch the console - it should NOT show Redis/MAVLink log messages")
    print("=" * 60)
    
    # Test Redis logging
    await test_redis_logging()
    
    # Test MAVLink logging
    test_mavlink_logging()
    
    print("=" * 60)
    print("✅ Test completed!")
    print("📋 Please check the following:")
    print("   1. Console output above should NOT contain Redis/MAVLink log messages")
    print("   2. app-redisproxy.log should contain Redis operation logs")
    print("   3. app-mavlinkexternalproxy.log should contain MAVLink connection logs")
    
    # Show log file contents
    for log_file in ["app-redisproxy.log", "app-mavlinkexternalproxy.log"]:
        if Path(log_file).exists():
            print(f"\n📄 Contents of {log_file}:")
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-5:]:  # Show last 5 lines
                    print(f"   {line.strip()}")
        else:
            print(f"\n⚠️  {log_file} was not created")

if __name__ == "__main__":
    asyncio.run(main())
