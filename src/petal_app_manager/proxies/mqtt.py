"""
MQTTProxy
=========

• Provides access to AWS IoT MQTT broker through TypeScript client API calls
• Handles callback server for receiving continuous message streams
• Abstracts MQTT communication details away from petals
• Provides async pub/sub operations with callback-style message handling

This proxy allows petals to interact with MQTT without worrying about
the underlying connection management and HTTP communication details.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Awaitable
import asyncio
import concurrent.futures
import json
import logging
import time
import os
import threading
from datetime import datetime
import functools

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from .base import BaseProxy
from .localdb import LocalDBProxy

class MessageCallback(BaseModel):
    """Model for incoming MQTT messages via callback"""
    topic: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
    qos: Optional[int] = None

class MQTTProxy(BaseProxy):
    """
    Proxy for communicating with AWS IoT MQTT through TypeScript client API calls.
    Provides callback-style message handling similar to RedisProxy pattern.
    """
    
    def __init__(
        self,
        local_db_proxy: LocalDBProxy,
        ts_client_host: str = "localhost",
        ts_client_port: int = 3004,
        callback_host: str = "localhost",
        callback_port: int = 3005,
        enable_callbacks: bool = True,
        debug: bool = False,
        request_timeout: int = 30
    ):
        self.ts_client_host = ts_client_host
        self.ts_client_port = ts_client_port
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.enable_callbacks = enable_callbacks
        self.debug = debug
        self.request_timeout = request_timeout
        self.local_db_proxy = local_db_proxy
        
        # For HTTP callback server
        self.callback_app = None
        self.callback_server = None
        self.callback_thread = None
        
        # Base URL for TypeScript client
        self.ts_base_url = f"http://{self.ts_client_host}:{self.ts_client_port}"
        self.callback_url = f"http://{self.callback_host}:{self.callback_port}/callback" if self.enable_callbacks else None
        
        # Subscription management (similar to RedisProxy pattern)
        self._subscriptions = {}  # topic: callback
        self._subscription_patterns = {}  # pattern: callback
        
        self.subscribed_topics = set()

        # Connection state
        self.is_connected = False
        self._shutdown_flag = False
        
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.log = logging.getLogger("MQTTProxy")

    async def start(self):
        """Initialize the MQTT proxy and start callback server."""
        
        # Get organization and device IDs
        self.organization_id = self._get_organization_id()
        self.robot_instance_id = self._get_machine_id()
        self.device_id = f"Instance-{self.robot_instance_id}" if self.robot_instance_id else None
        
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing MQTTProxy connection")
        
        # Validate configuration
        if not self.organization_id or not self.device_id:
            raise ValueError("Organization ID and Robot Instance ID must be available from LocalDBProxy")
        
        try:
            # Check TypeScript client health
            if not await self._check_ts_client_health():
                raise ConnectionError("TypeScript MQTT client is not accessible")
            
            # Setup and start callback server if enabled
            if self.enable_callbacks:
                await self._setup_callback_server()
                await self._start_callback_server()
            
            # Subscribe to default device topics
            await self._subscribe_to_device_topics()
            
            self.is_connected = True
            self.log.info("MQTTProxy started successfully")
            
        except Exception as e:
            self.log.error(f"Failed to initialize MQTTProxy: {e}")
            raise
        
    async def stop(self):
        """Clean up resources when shutting down."""
        self.log.info("Stopping MQTTProxy...")
        
        for topic in self.subscribed_topics:
            await self.unsubscribe_from_topic(topic)

        # Set shutdown flag
        self._shutdown_flag = True
        self.is_connected = False
        
        # Stop callback server
        if self.callback_server and self.enable_callbacks:
            try:
                self.callback_server.should_exit = True
                if self.callback_thread and self.callback_thread.is_alive():
                    self.callback_thread.join(timeout=5)
            except Exception as e:
                self.log.error(f"Error stopping callback server: {e}")
        
        # Shutdown executor
        if self._exe:
            self._exe.shutdown(wait=False)
            
        self.log.info("MQTTProxy stopped")

    def _get_machine_id(self) -> Optional[str]:
        """
        Get the machine ID from the LocalDBProxy.
        
        Returns:
            The machine ID if available, None otherwise
        """
        if not self.local_db_proxy:
            self.log.error("LocalDBProxy not available")
            return None
        
        machine_id = self.local_db_proxy.machine_id
        if not machine_id:
            self.log.error("Machine ID not available from LocalDBProxy")
            return None
        
        return machine_id

    def _get_organization_id(self) -> Optional[str]:
        """
        Get the organization ID from the LocalDBProxy.

        Returns:
            The organization ID if available, None otherwise
        """
        if not self.local_db_proxy:
            self.log.error("LocalDBProxy not available")
            return None

        organization_id = self.local_db_proxy.organization_id
        if not organization_id:
            self.log.error("Organization ID not available from LocalDBProxy")
            return None

        return organization_id

    # ------ TypeScript Client Communication ------ #
    
    async def _check_ts_client_health(self) -> bool:
        """Check if TypeScript MQTT client is healthy."""
        try:
            response = await self._loop.run_in_executor(
                self._exe,
                lambda: requests.get(f"{self.ts_base_url}/health", timeout=self.request_timeout)
            )
            return response.status_code == 200
        except Exception as e:
            self.log.error(f"TypeScript client health check failed: {e}")
            return False

    async def _make_ts_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to TypeScript client."""
        try:
            url = f"{self.ts_base_url}{endpoint}"
            
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                functools.partial(
                    requests.request,
                    method=method,
                    url=url,
                    json=data,
                    timeout=self.request_timeout,
                    headers={"Content-Type": "application/json"},
                ),
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"TypeScript client request failed: {response.status_code} - {response.text}"
                self.log.error(error_msg)
                return {"error": error_msg}
                
        except Exception as e:
            error_msg = f"Error communicating with TypeScript client: {str(e)}"
            self.log.error(error_msg)
            return {"error": error_msg}

    # ------ Callback Server Management ------ #
    
    async def _setup_callback_server(self):
        """Setup FastAPI callback server for receiving messages."""
        if not self.enable_callbacks:
            return

        self.callback_app = FastAPI(title="MQTT Callback Server")

        @self.callback_app.post('/callback')
        async def message_callback(message: MessageCallback):
            """Handle incoming MQTT messages."""
            try:
                await self._process_received_message(message.model_dump())
                return {"status": "success"}
            except Exception as e:
                self.log.error(f"Error processing callback message: {e}")
                return {"status": "error", "message": str(e)}

        @self.callback_app.get('/health')
        async def callback_health():
            """Health check for callback server."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

    async def _start_callback_server(self):
        """Start the callback server in a separate thread with Nagle disabled."""
        if not self.enable_callbacks or not self.callback_app:
            return

        def run_server():
            config = uvicorn.Config(
                self.callback_app,
                host=self.callback_host,
                port=self.callback_port,
                log_level="warning",  # Reduce log noise
                access_log=False,
                # Disable Nagle's algorithm for low latency
                loop="asyncio",
                http="h11"
            )
            server = uvicorn.Server(config)
            self.callback_server = server
            server.run()

        self.callback_thread = threading.Thread(target=run_server, daemon=True)
        self.callback_thread.start()
        
        # Wait a moment for server to start
        await asyncio.sleep(1)
        self.log.info(f"Callback server started on {self.callback_host}:{self.callback_port}")

    async def _process_received_message(self, message_data: Dict[str, Any]) -> None:
        """Process message received via callback (similar to RedisProxy pattern)."""
        try:
            topic = message_data.get('topic')
            payload = message_data.get('payload', {})
            
            if not topic:
                self.log.warning("Received message without topic")
                return

            self.log.debug(f"Processing MQTT message on topic: {topic}")

            # Check direct topic subscriptions
            if topic in self._subscriptions:
                callback = self._subscriptions[topic]
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(topic, payload)
                    else:
                        await self._loop.run_in_executor(self._exe, callback, topic, payload)
                except Exception as e:
                    self.log.error(f"Error in topic callback for {topic}: {e}")

            # Check pattern subscriptions
            for pattern, callback in self._subscription_patterns.items():
                if self._topic_matches_pattern(topic, pattern):
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(topic, payload)
                        else:
                            await self._loop.run_in_executor(self._exe, callback, topic, payload)
                    except Exception as e:
                        self.log.error(f"Error in pattern callback for {pattern}: {e}")

        except Exception as e:
            self.log.error(f"Error processing received message: {e}")

    @staticmethod
    def _topic_matches_pattern(topic: str, pattern: str) -> bool:
        """Simple pattern matching for MQTT topics (supports * wildcard)."""
        import fnmatch
        return fnmatch.fnmatch(topic, pattern)

    async def _subscribe_to_topic(self, topic: str, callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None) -> bool:
        """Subscribe to an MQTT topic via TypeScript client."""            
        try:
            request_data = {
                "topic": topic,
                "callbackUrl": self.callback_url if self.enable_callbacks else None
            }
            
            result = await self._make_ts_request("POST", "/subscribe", request_data)
            
            if "error" in result:
                self.log.error(f"Failed to subscribe to {topic}: {result['error']}")
                return False
            
            # Store callback if provided
            if callback:
                self._subscriptions[topic] = callback
            
            self.subscribed_topics.add(topic)

            self.log.info(f"Subscribed to topic: {topic}")
            return True
            
        except Exception as e:
            self.log.error(f"Error subscribing to {topic}: {e}")
            return False

    async def _subscribe_to_device_topics(self):
        """Subscribe to common device topics automatically."""
        if not self.organization_id or not self.device_id:
            self.log.warning("Cannot subscribe to device topics: missing org or device ID")
            return

        # Default topics to subscribe to
        topics = [
            f"org/{self.organization_id}/device/{self.device_id}/command",
            f"org/{self.organization_id}/device/{self.device_id}/response",
        ]

        for topic in topics:
            success = await self._subscribe_to_topic(topic, self._default_message_handler)
            if success:
                self.log.info(f"Auto-subscribed to device topic: {topic}")

    async def _default_message_handler(self, topic: str, payload: Dict[str, Any]):
        """Default message handler for device topics."""
        self.log.info(f"Received message on {topic}: {payload}")
        
        # Handle command messages
        if topic.endswith('/command'):
            await self._process_command(topic, payload)
        
    async def _process_command(self, topic: str, payload: Dict[str, Any]):
        """Enhanced command processing."""
        command_type = payload.get('command')
        message_id = payload.get('messageId', 'unknown')

        # Log command for audit
        self.log.info(f"Processing command: {payload}")

        # Send response back
        response_topic = topic.replace('/command', '/response')
        await self.send_command_response(response_topic, message_id, {
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })

    # ------ Public API methods ------ #
    
    async def publish_message(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        """Publish a message to an MQTT topic via TypeScript client."""
        if not self.is_connected:
            self.log.error("MQTT proxy is not connected")
            return False
            
        try:
            request_data = {
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "callbackUrl": self.callback_url
            }
            
            result = await self._make_ts_request("POST", "/publish", request_data)
            
            if "error" in result:
                self.log.error(f"Failed to publish message to {topic}: {result['error']}")
                return False
            
            self.log.debug(f"Published message to topic: {topic}")
            return True
            
        except Exception as e:
            self.log.error(f"Error publishing message to {topic}: {e}")
            return False

    async def subscribe_to_topic(self, topic: str, callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None) -> bool:
        """Subscribe to an MQTT topic via TypeScript client."""
        if not self.is_connected:
            self.log.error("MQTT proxy is not connected")
            return False
            
        return await self._subscribe_to_topic(topic, callback)

    async def unsubscribe_from_topic(self, topic: str) -> bool:
        """Unsubscribe from an MQTT topic."""
        if not self.is_connected:
            self.log.error("MQTT proxy is not connected")
            return False
            
        try:
            request_data = {"topic": topic}
            result = await self._make_ts_request("POST", "/unsubscribe", request_data)
            
            if "error" in result:
                self.log.error(f"Failed to unsubscribe from {topic}: {result['error']}")
                return False
            
            # Remove callback
            if topic in self._subscriptions:
                del self._subscriptions[topic]
            
            self.log.info(f"Unsubscribed from topic: {topic}")
            return True
            
        except Exception as e:
            self.log.error(f"Error unsubscribing from {topic}: {e}")
            return False

    def subscribe_pattern(self, pattern: str, callback: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        """Subscribe to topics matching a pattern (local pattern matching)."""
        self._subscription_patterns[pattern] = callback
        self.log.info(f"Registered pattern subscription: {pattern}")

    def unsubscribe_pattern(self, pattern: str):
        """Unsubscribe from a topic pattern."""
        if pattern in self._subscription_patterns:
            del self._subscription_patterns[pattern]
            self.log.info(f"Removed pattern subscription: {pattern}")

    async def send_command_response(self, response_topic: str, message_id: str, response_data: Dict[str, Any]) -> bool:
        """Send a command response."""
        response_payload = {
            'messageId': message_id,
            'timestamp': datetime.now().isoformat(),
            **response_data
        }
        
        return await self.publish_message(response_topic, response_payload)

    # ------ Health Check Methods ------ #
    
    async def health_check(self) -> Dict[str, Any]:
        """Check MQTT proxy health status."""
        health_status = {
            "status": "healthy" if self.is_connected else "unhealthy",
            "connection": {
                "ts_client": await self._check_ts_client_health(),
                "callback_server": self.enable_callbacks and self.callback_server is not None,
                "connected": self.is_connected
            },
            "configuration": {
                "ts_client_host": self.ts_client_host,
                "ts_client_port": self.ts_client_port,
                "callback_host": self.callback_host,
                "callback_port": self.callback_port,
                "enable_callbacks": self.enable_callbacks
            },
            "subscriptions": {
                "topics": list(self._subscriptions.keys()),
                "patterns": list(self._subscription_patterns.keys())
            },
            "device_info": {
                "organization_id": self.organization_id,
                "robot_instance_id": self.robot_instance_id
            }
        }
        
        return health_status