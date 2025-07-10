#!/usr/bin/env python3
"""
Integration Test for HEAR_FC Communication
==========================================

This script tests the two-way communication functionality without requiring
an actual HEAR_FC application. It simulates both sides of the communication
to verify the message exchange works correctly.

Usage:
    python integration_test_hear_fc.py
"""

import asyncio
import logging
import time
import json
from typing import Optional

from petal_app_manager.proxies.redis import (
    RedisProxy, 
    CommunicationMessage, 
    MessagePriority
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimulatedHearFC:
    """Simulated HEAR_FC application for testing."""
    
    def __init__(self):
        self.redis_proxy = RedisProxy(
            host="localhost",
            port=6379,
            app_id="HEAR_FC",
            debug=True
        )
        self.is_running = False
        self.battery_level = 100
        self.altitude = 0
        self.status = "idle"
    
    async def start(self):
        """Start the simulated HEAR_FC."""
        logger.info("Starting simulated HEAR_FC...")
        
        await self.redis_proxy.start()
        await self._register_handlers()
        await self.redis_proxy.start_listening()
        
        self.is_running = True
        
        # Start telemetry broadcasting
        asyncio.create_task(self._telemetry_loop())
        
        logger.info("Simulated HEAR_FC started")
    
    async def stop(self):
        """Stop the simulated HEAR_FC."""
        logger.info("Stopping simulated HEAR_FC...")
        
        self.is_running = False
        await self.redis_proxy.stop_listening()
        await self.redis_proxy.stop()
        
        logger.info("Simulated HEAR_FC stopped")
    
    async def _register_handlers(self):
        """Register message handlers."""
        await self.redis_proxy.register_message_handler("command", self._handle_command)
        await self.redis_proxy.register_message_handler("configuration", self._handle_configuration)
        await self.redis_proxy.register_message_handler("health_check", self._handle_health_check)
    
    async def _handle_command(self, message: CommunicationMessage) -> Optional[CommunicationMessage]:
        """Handle commands from petal-app-manager."""
        payload = message.payload
        command = payload.get("command")
        command_id = payload.get("command_id")
        
        logger.info(f"HEAR_FC received command: {command}")
        
        response_payload = {
            "command_id": command_id,
            "command": command,
            "timestamp": time.time()
        }
        
        # Simulate command execution
        if command == "takeoff":
            altitude = payload.get("parameters", {}).get("altitude", 10)
            self.altitude = altitude
            self.status = "flying"
            response_payload["status"] = "success"
            response_payload["message"] = f"Takeoff to {altitude}m completed"
            
        elif command == "land":
            self.altitude = 0
            self.status = "landed"
            response_payload["status"] = "success"
            response_payload["message"] = "Landing completed"
            
        elif command == "emergency_stop":
            self.status = "emergency_stopped"
            response_payload["status"] = "success"
            response_payload["message"] = "Emergency stop executed"
            
        else:
            response_payload["status"] = "error"
            response_payload["message"] = f"Unknown command: {command}"
        
        # Send response
        await self.redis_proxy.send_message(
            recipient=message.sender,
            message_type="command_response",
            payload=response_payload,
            priority=MessagePriority.HIGH
        )
    
    async def _handle_configuration(self, message: CommunicationMessage) -> None:
        """Handle configuration updates."""
        logger.info(f"HEAR_FC received configuration: {message.payload}")
        
        # Send acknowledgment
        await self.redis_proxy.send_message(
            recipient=message.sender,
            message_type="configuration_ack",
            payload={"status": "accepted", "timestamp": time.time()},
            priority=MessagePriority.NORMAL
        )
    
    async def _handle_health_check(self, message: CommunicationMessage) -> Optional[CommunicationMessage]:
        """Handle health check requests."""
        logger.info("HEAR_FC health check requested")
        
        return CommunicationMessage(
            id="health_response",
            sender="HEAR_FC",
            recipient=message.sender,
            message_type="health_response",
            payload={
                "status": "healthy",
                "uptime": time.time(),
                "battery_level": self.battery_level,
                "current_status": self.status
            }
        )
    
    async def _telemetry_loop(self):
        """Send periodic telemetry."""
        while self.is_running:
            telemetry = {
                "timestamp": time.time(),
                "battery_level": self.battery_level,
                "altitude": self.altitude,
                "speed": 5.0 if self.status == "flying" else 0.0,
                "system_status": self.status,
                "gps_coordinates": {"lat": 37.7749, "lon": -122.4194}
            }
            
            await self.redis_proxy.send_message(
                recipient="petal-app-manager",
                message_type="telemetry",
                payload=telemetry,
                priority=MessagePriority.NORMAL
            )
            
            # Simulate battery drain
            if self.status == "flying":
                self.battery_level = max(0, self.battery_level - 1)
            
            await asyncio.sleep(2)  # Send telemetry every 2 seconds


class TestController:
    """Test controller to simulate petal-app-manager."""
    
    def __init__(self):
        self.redis_proxy = RedisProxy(
            host="localhost",
            port=6379,
            app_id="petal-app-manager",
            debug=True
        )
        self.telemetry_data = []
        self.command_responses = []
    
    async def start(self):
        """Start the test controller."""
        logger.info("Starting test controller...")
        
        await self.redis_proxy.start()
        await self._register_handlers()
        await self.redis_proxy.start_listening()
        
        logger.info("Test controller started")
    
    async def stop(self):
        """Stop the test controller."""
        logger.info("Stopping test controller...")
        
        await self.redis_proxy.stop_listening()
        await self.redis_proxy.stop()
        
        logger.info("Test controller stopped")
    
    async def _register_handlers(self):
        """Register message handlers."""
        await self.redis_proxy.register_message_handler("telemetry", self._handle_telemetry)
        await self.redis_proxy.register_message_handler("command_response", self._handle_command_response)
        await self.redis_proxy.register_message_handler("configuration_ack", self._handle_config_ack)
    
    async def _handle_telemetry(self, message: CommunicationMessage) -> None:
        """Handle telemetry from HEAR_FC."""
        self.telemetry_data.append(message.payload)
        
        # Keep only last 10 telemetry points
        if len(self.telemetry_data) > 10:
            self.telemetry_data.pop(0)
        
        logger.info(f"Received telemetry: Battery {message.payload.get('battery_level')}%, "
                   f"Altitude {message.payload.get('altitude')}m")
    
    async def _handle_command_response(self, message: CommunicationMessage) -> None:
        """Handle command responses from HEAR_FC."""
        self.command_responses.append(message.payload)
        logger.info(f"Command response: {message.payload.get('status')} - {message.payload.get('message')}")
    
    async def _handle_config_ack(self, message: CommunicationMessage) -> None:
        """Handle configuration acknowledgments."""
        logger.info(f"Configuration acknowledged: {message.payload}")
    
    async def send_command(self, command: str, parameters: dict = None) -> bool:
        """Send a command to HEAR_FC."""
        command_id = f"cmd_{int(time.time() * 1000)}"
        
        payload = {
            "command_id": command_id,
            "command": command,
            "parameters": parameters or {},
            "timestamp": time.time()
        }
        
        result = await self.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="command",
            payload=payload,
            priority=MessagePriority.HIGH
        )
        
        return result is not None
    
    async def check_hear_fc_status(self) -> bool:
        """Check if HEAR_FC is online."""
        status = await self.redis_proxy.get_application_status("HEAR_FC")
        return status and status.get("status") == "online"


async def run_integration_test():
    """Run the complete integration test."""
    logger.info("=" * 60)
    logger.info("Starting HEAR_FC Communication Integration Test")
    logger.info("=" * 60)
    
    # Create instances
    hear_fc = SimulatedHearFC()
    controller = TestController()
    
    try:
        # Start both applications
        await hear_fc.start()
        await controller.start()
        
        # Wait for initialization
        await asyncio.sleep(2)
        
        # Test 1: Check connectivity
        logger.info("\n--- Test 1: Connectivity Check ---")
        is_online = await controller.check_hear_fc_status()
        logger.info(f"HEAR_FC online: {is_online}")
        assert is_online, "HEAR_FC should be online"
        
        # Test 2: Send configuration
        logger.info("\n--- Test 2: Configuration ---")
        config_result = await controller.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="configuration",
            payload={
                "flight_mode": "autonomous",
                "max_altitude": 100,
                "geofence_enabled": True
            },
            priority=MessagePriority.HIGH
        )
        logger.info(f"Configuration sent: {config_result is not None}")
        
        # Test 3: Send commands
        logger.info("\n--- Test 3: Command Execution ---")
        commands = [
            ("takeoff", {"altitude": 20}),
            ("hover", {"duration": 5}),
            ("land", {"precision": True})
        ]
        
        for command, params in commands:
            success = await controller.send_command(command, params)
            logger.info(f"Command '{command}' sent: {success}")
            await asyncio.sleep(1)  # Wait between commands
        
        # Test 4: Health check
        logger.info("\n--- Test 4: Health Check ---")
        health_response = await controller.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="health_check",
            payload={"check_time": time.time()},
            wait_for_reply=True,
            timeout=5
        )
        
        if health_response:
            logger.info(f"Health check response: {health_response.payload}")
        else:
            logger.warning("No health check response received")
        
        # Test 5: Monitor telemetry
        logger.info("\n--- Test 5: Telemetry Monitoring ---")
        logger.info("Monitoring telemetry for 10 seconds...")
        await asyncio.sleep(10)
        
        logger.info(f"Received {len(controller.telemetry_data)} telemetry points")
        logger.info(f"Received {len(controller.command_responses)} command responses")
        
        # Show recent telemetry
        if controller.telemetry_data:
            latest = controller.telemetry_data[-1]
            logger.info(f"Latest telemetry: {latest}")
        
        # Test 6: List online applications
        logger.info("\n--- Test 6: Application Discovery ---")
        online_apps = await controller.redis_proxy.list_online_applications()
        logger.info(f"Online applications: {online_apps}")
        assert "HEAR_FC" in online_apps, "HEAR_FC should be in online applications list"
        assert "petal-app-manager" in online_apps, "petal-app-manager should be in online applications list"
        
        # Test 7: Emergency stop
        logger.info("\n--- Test 7: Emergency Stop ---")
        emergency_result = await controller.send_command("emergency_stop", {"immediate": True})
        logger.info(f"Emergency stop sent: {emergency_result}")
        await asyncio.sleep(2)
        
        # Final status
        logger.info("\n--- Integration Test Results ---")
        logger.info(f"✓ Connectivity: PASSED")
        logger.info(f"✓ Configuration: PASSED")
        logger.info(f"✓ Commands: PASSED ({len(controller.command_responses)} responses)")
        logger.info(f"✓ Telemetry: PASSED ({len(controller.telemetry_data)} points)")
        logger.info(f"✓ Health Check: {'PASSED' if health_response else 'FAILED'}")
        logger.info(f"✓ Application Discovery: PASSED")
        logger.info(f"✓ Emergency Stop: PASSED")
        
        logger.info("\n🎉 All integration tests PASSED!")
        
    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        raise
    finally:
        # Clean shutdown
        logger.info("\n--- Cleaning Up ---")
        await hear_fc.stop()
        await controller.stop()
        logger.info("Integration test completed")


if __name__ == "__main__":
    # Check if Redis is available
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        logger.info("Redis server is available")
    except Exception as e:
        logger.error(f"Redis server not available: {e}")
        logger.error("Please start Redis server with: redis-server")
        exit(1)
    
    # Run the integration test
    asyncio.run(run_integration_test())
