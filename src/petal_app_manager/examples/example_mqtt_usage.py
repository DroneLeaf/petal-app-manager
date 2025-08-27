#!/usr/bin/env python3
"""
Example MQTT Usage for Petal App Manager
========================================

This example demonstrates how to use the MQTTProxy integrated into the 
Petal App Manager to:

1. Publish messages to MQTT topics
2. Subscribe to topics with custom callbacks
3. Handle incoming command messages
4. Use pattern subscriptions for topic filtering

The MQTTProxy communicates with a TypeScript MQTT client via HTTP API calls
and provides callback-style message handling similar to the RedisProxy pattern.
"""

import asyncio
import logging
import requests
import json
from datetime import datetime
from typing import Dict, Any

# Configuration for MQTT proxy endpoints
PETAL_APP_MANAGER_URL = "http://localhost:8000"  # Your FastAPI server
MQTT_API_BASE = f"{PETAL_APP_MANAGER_URL}/mqtt"

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MQTTExampleClient:
    """Example client for demonstrating MQTT functionality."""
    
    def __init__(self, base_url: str = MQTT_API_BASE):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def publish_message(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        """Publish a message to an MQTT topic."""
        try:
            response = self.session.post(
                f"{self.base_url}/publish",
                json={
                    "topic": topic,
                    "payload": payload,
                    "qos": qos
                }
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Published to {topic}: {result}")
            return result.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
    
    def subscribe_to_topic(self, topic: str) -> bool:
        """Subscribe to an MQTT topic."""
        try:
            response = self.session.post(
                f"{self.base_url}/subscribe",
                json={"topic": topic}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Subscribed to {topic}: {result}")
            return result.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to subscribe to topic: {e}")
            return False
    
    def unsubscribe_from_topic(self, topic: str) -> bool:
        """Unsubscribe from an MQTT topic."""
        try:
            response = self.session.post(
                f"{self.base_url}/unsubscribe",
                json={"topic": topic}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Unsubscribed from {topic}: {result}")
            return result.get("status") == "success"
        except Exception as e:
            logger.error(f"Failed to unsubscribe from topic: {e}")
            return False
    
    def get_mqtt_status(self) -> Dict[str, Any]:
        """Get MQTT proxy status."""
        try:
            response = self.session.get(f"{self.base_url}/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get MQTT status: {e}")
            return {}
    
    def list_subscriptions(self) -> Dict[str, Any]:
        """List current MQTT subscriptions."""
        try:
            response = self.session.get(f"{self.base_url}/subscriptions")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to list subscriptions: {e}")
            return {}

def example_basic_usage():
    """Demonstrate basic MQTT operations."""
    logger.info("=== Basic MQTT Usage Example ===")
    
    client = MQTTExampleClient()
    
    # Check MQTT proxy status
    logger.info("Checking MQTT proxy status...")
    status = client.get_mqtt_status()
    if status:
        logger.info(f"MQTT Status: {status.get('status')}")
        logger.info(f"Device Info: {status.get('device_info', {})}")
    
    # Subscribe to a test topic
    test_topic = "test/example/messages"
    logger.info(f"Subscribing to topic: {test_topic}")
    if client.subscribe_to_topic(test_topic):
        logger.info("Successfully subscribed!")
    
    # Publish a test message
    test_payload = {
        "message": "Hello from Petal App Manager!",
        "timestamp": datetime.now().isoformat(),
        "source": "example_client",
        "data": {
            "temperature": 23.5,
            "humidity": 65.2,
            "status": "operational"
        }
    }
    
    logger.info(f"Publishing test message to {test_topic}")
    if client.publish_message(test_topic, test_payload):
        logger.info("Message published successfully!")
    
    # List current subscriptions
    logger.info("Listing current subscriptions...")
    subscriptions = client.list_subscriptions()
    if subscriptions:
        logger.info(f"Active subscriptions: {subscriptions}")

def example_device_communication():
    """Demonstrate device command/response communication pattern."""
    logger.info("=== Device Communication Example ===")
    
    client = MQTTExampleClient()
    
    # Get device info from status
    status = client.get_mqtt_status()
    device_info = status.get('device_info', {})
    org_id = device_info.get('organization_id')
    device_id = device_info.get('robot_instance_id')
    
    if not org_id or not device_id:
        logger.error("Could not get organization or device ID from MQTT proxy")
        return
    
    logger.info(f"Using org_id: {org_id}, device_id: {device_id}")
    
    # Device topic patterns
    command_topic = f"org/{org_id}/device/{device_id}/command"
    response_topic = f"org/{org_id}/device/{device_id}/response"
    telemetry_topic = f"org/{org_id}/device/{device_id}/telemetry"
    
    # The device automatically subscribes to command topics,
    # so we can directly publish commands
    
    # Send a command to the device
    command_payload = {
        "command": "get_status",
        "messageId": f"cmd_{int(datetime.now().timestamp())}",
        "timestamp": datetime.now().isoformat(),
        "parameters": {
            "include_telemetry": True,
            "format": "detailed"
        }
    }
    
    logger.info(f"Sending command to device via {command_topic}")
    if client.publish_message(command_topic, command_payload):
        logger.info("Command sent successfully!")
    
    # Publish some telemetry data
    telemetry_payload = {
        "messageId": f"tel_{int(datetime.now().timestamp())}",
        "timestamp": datetime.now().isoformat(),
        "telemetry": {
            "battery_level": 85.5,
            "gps_location": {
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 100.5
            },
            "system_status": {
                "cpu_usage": 25.3,
                "memory_usage": 45.8,
                "disk_usage": 60.2
            },
            "sensors": {
                "temperature": 22.1,
                "humidity": 58.7,
                "pressure": 1013.25
            }
        }
    }
    
    logger.info(f"Publishing telemetry data to {telemetry_topic}")
    if client.publish_message(telemetry_topic, telemetry_payload):
        logger.info("Telemetry published successfully!")

def example_monitoring():
    """Demonstrate monitoring and status checking."""
    logger.info("=== MQTT Monitoring Example ===")
    
    client = MQTTExampleClient()
    
    # Get comprehensive status
    logger.info("Getting comprehensive MQTT status...")
    status = client.get_mqtt_status()
    
    if status:
        print(json.dumps(status, indent=2))
        
        # Check connection health
        connection = status.get('connection', {})
        if connection.get('connected'):
            logger.info("✅ MQTT proxy is connected and healthy")
        else:
            logger.warning("⚠️ MQTT proxy connection issues detected")
        
        # Check callback server
        if connection.get('callback_server'):
            logger.info("✅ Callback server is running")
        else:
            logger.warning("⚠️ Callback server is not available")
        
        # Check TypeScript client
        if connection.get('ts_client'):
            logger.info("✅ TypeScript MQTT client is accessible")
        else:
            logger.warning("⚠️ TypeScript MQTT client is not accessible")
    
    # List current subscriptions
    logger.info("Getting current subscriptions...")
    subscriptions = client.list_subscriptions()
    
    if subscriptions:
        topic_count = len(subscriptions.get('topics', []))
        pattern_count = len(subscriptions.get('patterns', []))
        logger.info(f"📊 Active subscriptions: {topic_count} topics, {pattern_count} patterns")
        
        if subscriptions.get('topics'):
            logger.info("Topics:")
            for topic in subscriptions['topics']:
                logger.info(f"  - {topic}")
        
        if subscriptions.get('patterns'):
            logger.info("Patterns:")
            for pattern in subscriptions['patterns']:
                logger.info(f"  - {pattern}")

def main():
    """Run all examples."""
    logger.info("Starting MQTT Examples for Petal App Manager")
    logger.info("=" * 50)
    
    try:
        # Run examples
        example_basic_usage()
        print()
        example_device_communication()
        print()
        example_monitoring()
        
        logger.info("=" * 50)
        logger.info("All examples completed successfully!")
        
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise

if __name__ == "__main__":
    main()
