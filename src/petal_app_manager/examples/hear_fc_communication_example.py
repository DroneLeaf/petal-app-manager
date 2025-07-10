#!/usr/bin/env python3
"""
HEAR_FC Communication Example
============================

This example demonstrates how to use the RedisProxy for two-way communication
with the HEAR_FC C++ application. It shows:

1. Setting up the communication system
2. Registering message handlers
3. Sending commands and requests
4. Receiving telemetry and responses
5. Monitoring application status

Usage:
    python hear_fc_communication_example.py
"""

import asyncio
import logging
import time
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


class HearFCCommunicator:
    """Example communication manager for HEAR_FC integration."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_proxy = RedisProxy(
            host=redis_host,
            port=redis_port,
            app_id="petal-app-manager",
            debug=True
        )
        self.telemetry_data = []
        self.command_responses = {}
        self.is_running = False
    
    async def start(self):
        """Initialize the communication system."""
        logger.info("Starting HEAR_FC communicator...")
        
        # Start Redis proxy
        await self.redis_proxy.start()
        
        # Register message handlers
        await self._register_handlers()
        
        # Start listening for messages
        await self.redis_proxy.start_listening()
        
        self.is_running = True
        logger.info("HEAR_FC communicator started successfully")
    
    async def stop(self):
        """Stop the communication system."""
        logger.info("Stopping HEAR_FC communicator...")
        
        self.is_running = False
        
        # Stop listening and close connections
        await self.redis_proxy.stop_listening()
        await self.redis_proxy.stop()
        
        logger.info("HEAR_FC communicator stopped")
    
    async def _register_handlers(self):
        """Register handlers for different message types from HEAR_FC."""
        
        # Handle telemetry data
        await self.redis_proxy.register_message_handler(
            "telemetry", 
            self._handle_telemetry
        )
        
        # Handle command responses
        await self.redis_proxy.register_message_handler(
            "command_response", 
            self._handle_command_response
        )
        
        # Handle status updates
        await self.redis_proxy.register_message_handler(
            "status_update", 
            self._handle_status_update
        )
        
        # Handle alerts/warnings
        await self.redis_proxy.register_message_handler(
            "alert", 
            self._handle_alert
        )
        
        # Handle health checks
        await self.redis_proxy.register_message_handler(
            "health_check", 
            self._handle_health_check
        )
    
    async def _handle_telemetry(self, message: CommunicationMessage) -> None:
        """Handle telemetry data from HEAR_FC."""
        payload = message.payload
        
        # Store telemetry data
        self.telemetry_data.append({
            'timestamp': payload.get('timestamp', time.time()),
            'battery_level': payload.get('battery_level'),
            'gps_coordinates': payload.get('gps_coordinates'),
            'altitude': payload.get('altitude'),
            'speed': payload.get('speed'),
            'orientation': payload.get('orientation'),
            'system_status': payload.get('system_status')
        })
        
        # Keep only last 100 telemetry points
        if len(self.telemetry_data) > 100:
            self.telemetry_data.pop(0)
        
        logger.info(f"Received telemetry: Battery {payload.get('battery_level')}%, "
                   f"Altitude {payload.get('altitude')}m")
        
        # Check for critical conditions
        if payload.get('battery_level', 100) < 20:
            logger.warning("Low battery warning from HEAR_FC!")
        
        if payload.get('system_status') == 'error':
            logger.error("System error reported by HEAR_FC!")
    
    async def _handle_command_response(self, message: CommunicationMessage) -> None:
        """Handle command responses from HEAR_FC."""
        payload = message.payload
        command_id = payload.get('command_id')
        
        if command_id:
            self.command_responses[command_id] = payload
        
        logger.info(f"Command response: {payload.get('status')} - {payload.get('message')}")
    
    async def _handle_status_update(self, message: CommunicationMessage) -> None:
        """Handle status updates from HEAR_FC."""
        payload = message.payload
        logger.info(f"HEAR_FC status update: {payload}")
    
    async def _handle_alert(self, message: CommunicationMessage) -> None:
        """Handle alerts from HEAR_FC."""
        payload = message.payload
        severity = payload.get('severity', 'info')
        alert_message = payload.get('message', 'Unknown alert')
        
        if severity == 'critical':
            logger.critical(f"CRITICAL ALERT from HEAR_FC: {alert_message}")
        elif severity == 'warning':
            logger.warning(f"WARNING from HEAR_FC: {alert_message}")
        else:
            logger.info(f"INFO from HEAR_FC: {alert_message}")
    
    async def _handle_health_check(self, message: CommunicationMessage) -> Optional[CommunicationMessage]:
        """Respond to health checks from HEAR_FC."""
        logger.info("Health check request from HEAR_FC")
        
        # Return health status
        return CommunicationMessage(
            id="health_response",
            sender="petal-app-manager",
            recipient="HEAR_FC",
            message_type="health_response",
            payload={
                "status": "healthy",
                "uptime": time.time(),
                "services_running": ["redis_proxy", "message_handler"],
                "memory_usage": "normal"
            }
        )
    
    # ------ Public API Methods ------ #
    
    async def check_hear_fc_status(self) -> bool:
        """Check if HEAR_FC is online and responsive."""
        status = await self.redis_proxy.get_application_status("HEAR_FC")
        
        if not status:
            logger.warning("HEAR_FC not found in Redis")
            return False
        
        if status.get("status") != "online":
            logger.warning(f"HEAR_FC status: {status.get('status')}")
            return False
        
        logger.info("HEAR_FC is online and responsive")
        return True
    
    async def send_command(self, command: str, parameters: dict = None, 
                          wait_for_response: bool = False, timeout: int = 10) -> dict:
        """
        Send a command to HEAR_FC.
        
        Args:
            command: Command name (e.g., 'takeoff', 'land', 'goto')
            parameters: Command parameters
            wait_for_response: Whether to wait for command acknowledgment
            timeout: Response timeout in seconds
            
        Returns:
            Command response if wait_for_response=True, empty dict otherwise
        """
        command_id = f"cmd_{int(time.time() * 1000)}"
        
        payload = {
            "command_id": command_id,
            "command": command,
            "parameters": parameters or {},
            "timestamp": time.time()
        }
        
        logger.info(f"Sending command to HEAR_FC: {command}")
        
        response = await self.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="command",
            payload=payload,
            priority=MessagePriority.HIGH,
            wait_for_reply=wait_for_response,
            timeout=timeout
        )
        
        if wait_for_response and response:
            return response.payload
        elif wait_for_response:
            logger.warning(f"No response received for command {command} within {timeout}s")
            return {"status": "timeout", "command_id": command_id}
        
        return {"status": "sent", "command_id": command_id}
    
    async def request_telemetry(self, fields: list = None) -> bool:
        """Request specific telemetry fields from HEAR_FC."""
        payload = {
            "request_type": "telemetry",
            "fields": fields or ["battery", "gps", "altitude", "speed", "orientation"],
            "frequency": "1hz"  # Request 1Hz updates
        }
        
        response = await self.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="telemetry_request",
            payload=payload,
            priority=MessagePriority.NORMAL
        )
        
        return response is not None
    
    async def configure_hear_fc(self, config: dict) -> dict:
        """Send configuration to HEAR_FC."""
        response = await self.redis_proxy.send_message(
            recipient="HEAR_FC",
            message_type="configuration",
            payload=config,
            priority=MessagePriority.HIGH,
            wait_for_reply=True,
            timeout=15
        )
        
        if response:
            return response.payload
        return {"status": "timeout"}
    
    async def emergency_stop(self) -> dict:
        """Send emergency stop command to HEAR_FC."""
        logger.critical("Sending EMERGENCY STOP to HEAR_FC!")
        
        response = await self.send_command(
            command="emergency_stop",
            parameters={"immediate": True},
            wait_for_response=True,
            timeout=5
        )
        
        return response
    
    def get_latest_telemetry(self) -> dict:
        """Get the most recent telemetry data."""
        if self.telemetry_data:
            return self.telemetry_data[-1]
        return {}
    
    def get_telemetry_history(self, count: int = 10) -> list:
        """Get recent telemetry history."""
        return self.telemetry_data[-count:] if self.telemetry_data else []


async def main():
    """Example usage of the HEAR_FC communication system."""
    communicator = HearFCCommunicator()
    
    try:
        # Start the communication system
        await communicator.start()
        
        # Wait a moment for system to initialize
        await asyncio.sleep(1)
        
        # Check if HEAR_FC is online
        is_online = await communicator.check_hear_fc_status()
        if not is_online:
            logger.warning("HEAR_FC is not online. Starting in demo mode...")
        
        # Send initial configuration
        config = {
            "flight_mode": "autonomous",
            "max_altitude": 100,  # meters
            "max_speed": 10,      # m/s
            "geofence": {
                "enabled": True,
                "center": {"lat": 37.7749, "lon": -122.4194},
                "radius": 1000  # meters
            },
            "safety": {
                "battery_low_threshold": 20,  # percent
                "auto_land_enabled": True,
                "emergency_procedures": ["auto_land", "notify_operator"]
            }
        }
        
        config_response = await communicator.configure_hear_fc(config)
        logger.info(f"Configuration response: {config_response}")
        
        # Request telemetry updates
        await communicator.request_telemetry([
            "battery_level", "gps_coordinates", "altitude", 
            "speed", "orientation", "system_status"
        ])
        
        # Example mission commands
        commands = [
            ("preflight_check", {"systems": ["gps", "battery", "sensors"]}),
            ("arm", {"safety_checks": True}),
            ("takeoff", {"altitude": 20}),
            ("goto", {"lat": 37.7750, "lon": -122.4195, "altitude": 25}),
            ("hover", {"duration": 10}),
            ("return_to_launch", {}),
            ("land", {"precision": True}),
            ("disarm", {})
        ]
        
        # Execute commands with delays
        for command, params in commands:
            logger.info(f"Executing command: {command}")
            
            result = await communicator.send_command(
                command=command,
                parameters=params,
                wait_for_response=True,
                timeout=10
            )
            
            logger.info(f"Command {command} result: {result}")
            
            # Wait between commands
            await asyncio.sleep(2)
            
            # Check latest telemetry
            telemetry = communicator.get_latest_telemetry()
            if telemetry:
                logger.info(f"Current telemetry: {telemetry}")
        
        # Run for a while to receive telemetry
        logger.info("Monitoring telemetry for 30 seconds...")
        await asyncio.sleep(30)
        
        # Show telemetry history
        history = communicator.get_telemetry_history(5)
        logger.info(f"Recent telemetry history: {len(history)} points")
        for i, point in enumerate(history):
            logger.info(f"  {i+1}: {point}")
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal...")
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        # Clean shutdown
        await communicator.stop()


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
