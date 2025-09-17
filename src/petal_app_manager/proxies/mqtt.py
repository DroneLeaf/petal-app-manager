"""
MQTTProxy
=========

• Provides access to AWS IoT MQTT broker through TypeScript client API calls
• Handles callback server for receiving continuous message streams
• Uses deque-based message buffering with multi-threaded processing
• Abstracts MQTT communication details away from petals
• Provides async pub/sub operations with callback-style message handling

This proxy allows petals to interact with MQTT without worrying about
the underlying connection management and HTTP communication details.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Awaitable, Deque
from collections import deque, defaultdict
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
from ..organization_manager import get_organization_manager

class MQTTMessage:
    """Internal message structure for deque processing."""
    def __init__(self, topic: str, payload: Dict[str, Any], timestamp: Optional[str] = None, qos: Optional[int] = None):
        self.topic = topic
        self.payload = payload
        self.timestamp = timestamp or datetime.now().isoformat()
        self.qos = qos

class MessageCallback(BaseModel):
    """Model for incoming MQTT messages via callback"""
    topic: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
    qos: Optional[int] = None

class MQTTProxy(BaseProxy):
    """
    Proxy for communicating with AWS IoT MQTT through TypeScript client API calls.
    Uses deque-based message buffering with multi-threaded callback processing.
    """
    
    def __init__(
        self,
        ts_client_host: str = "localhost",
        ts_client_port: int = 3004,
        callback_host: str = "localhost",
        callback_port: int = 3005,
        enable_callbacks: bool = True,
        debug: bool = False,
        request_timeout: int = 30,
        max_message_buffer: int = 1000,
        worker_threads: int = 4,
        worker_sleep_ms: float = 10.0
    ):
        self.ts_client_host = ts_client_host
        self.ts_client_port = ts_client_port
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.enable_callbacks = enable_callbacks
        self.debug = debug
        self.request_timeout = request_timeout
        
        # Message buffer configuration
        self.max_message_buffer = max_message_buffer
        self.worker_threads = worker_threads
        self.worker_sleep_ms = worker_sleep_ms
        
        # For HTTP callback server
        self.callback_app = None
        self.callback_server = None
        self.callback_thread = None
        
        # Base URL for TypeScript client
        self.ts_base_url = f"http://{self.ts_client_host}:{self.ts_client_port}"
        self.callback_url = f"http://{self.callback_host}:{self.callback_port}/callback" if self.enable_callbacks else None
        
        # Message buffering system (similar to MavlinkExternalProxy)
        self._message_buffer: Deque[MQTTMessage] = deque(maxlen=self.max_message_buffer)
        self._buffer_lock = threading.Lock()
        
        # Subscription management
        self._subscriptions = {}  # topic: callback
        self._subscription_patterns = {}  # pattern: callback
        self._handlers: Dict[str, List[Callable[[str, Dict[str, Any]], None]]] = defaultdict(list)
        
        self.subscribed_topics = set()

        # Connection and worker thread state
        self.is_connected = False
        self._shutdown_flag = False
        self._worker_running = threading.Event()
        self._worker_threads = []
        
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=self.worker_threads)
        self.log = logging.getLogger("MQTTProxy")

    async def start(self):
        """Initialize the MQTT proxy and start callback server and worker threads."""
        
        # Get robot instance ID for basic setup
        self.robot_instance_id = self._get_machine_id()
        self.device_id = f"Instance-{self.robot_instance_id}" if self.robot_instance_id else None
        
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing MQTTProxy connection")
        
        # Validate basic configuration (organization_id will be fetched on-demand)
        if not self.device_id:
            raise ValueError("Robot Instance ID must be available from OrganizationManager")
        
        try:
            # Check TypeScript client health
            if not await self._check_ts_client_health():
                raise ConnectionError("TypeScript MQTT client is not accessible")
            
            # Start worker threads for message processing
            self._start_worker_threads()
            
            # Setup and start callback server if enabled
            if self.enable_callbacks:
                await self._setup_callback_server()
                await self._start_callback_server()
            
            # Subscribe to default device topics (will get org_id on-demand)
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
        self._worker_running.clear()
        self.is_connected = False
        
        # Stop worker threads
        await self._stop_worker_threads()
        
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
        Get the machine ID from the OrganizationManager.
        
        Returns:
            The machine ID if available, None otherwise
        """
        try:
            org_manager = get_organization_manager()
            machine_id = org_manager.machine_id
            if not machine_id:
                self.log.error("Machine ID not available from OrganizationManager")
                return None
            return machine_id
        except Exception as e:
            self.log.error(f"Error getting machine ID from OrganizationManager: {e}")
            return None

    def _get_organization_id(self) -> Optional[str]:
        """
        Get the organization ID from the OrganizationManager on-demand.

        Returns:
            The organization ID if available, None otherwise
        """
        try:
            org_manager = get_organization_manager()
            org_id = org_manager.organization_id
            if not org_id:
                self.log.debug("Organization ID not yet available from OrganizationManager")
                return None
            return org_id
        except Exception as e:
            self.log.debug(f"Error getting organization ID from OrganizationManager: {e}")
            return None
    
    def _get_organization_id_with_wait(self, timeout: float = 5.0) -> Optional[str]:
        """
        Get organization ID with optional wait for availability.
        
        Args:
            timeout: Maximum time to wait for organization ID
            
        Returns:
            Organization ID if available within timeout, None otherwise
        """
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            org_id = self._get_organization_id()
            if org_id:
                return org_id
            time.sleep(0.5)
        
        self.log.warning(f"Organization ID not available after {timeout}s timeout")
        return None

    @property
    def organization_id(self) -> Optional[str]:
        """
        Organization ID property for backward compatibility.
        Fetches organization_id on-demand from OrganizationManager.
        
        Returns:
            Organization ID if available, None otherwise
        """
        return self._get_organization_id()

    # ------ Worker Thread Management ------ #

    def _start_worker_threads(self):
        """Start worker threads for processing message buffer."""
        self._worker_running.set()
        
        for i in range(self.worker_threads):
            worker_thread = threading.Thread(
                target=self._worker_thread_main,
                name=f"MQTTProxy-Worker-{i}",
                daemon=True
            )
            worker_thread.start()
            self._worker_threads.append(worker_thread)
            
        self.log.info(f"Started {self.worker_threads} worker threads for message processing")

    async def _stop_worker_threads(self):
        """Stop all worker threads gracefully."""
        self._worker_running.clear()
        
        # Wait for threads to finish
        for thread in self._worker_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
                
        self._worker_threads.clear()
        self.log.info("Stopped all worker threads")

    def _worker_thread_main(self):
        """Main loop for worker threads - processes messages from buffer."""
        sleep_time = self.worker_sleep_ms / 1000.0
        
        while self._worker_running.is_set():
            try:
                # Get message from buffer
                message = self._get_next_message()
                
                if message:
                    self._process_message_in_worker(message)
                else:
                    # No messages, sleep briefly
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.log.error(f"Error in worker thread: {e}")
                time.sleep(sleep_time)

    def _get_next_message(self) -> Optional[MQTTMessage]:
        """Thread-safe method to get next message from buffer."""
        with self._buffer_lock:
            if self._message_buffer:
                return self._message_buffer.popleft()
        return None

    def _enqueue_message(self, message: MQTTMessage):
        """Thread-safe method to add message to buffer."""
        with self._buffer_lock:
            msg_id = message.payload.get("messageId")
            # make sure there are no duplicate messages in queue

            if msg_id:
                # Check for duplicates
                for existing_msg in self._message_buffer:
                    if existing_msg.payload.get("messageId") == msg_id:
                        self.log.debug(f"Duplicate message detected: {msg_id}")
                        return  # Drop duplicate message

            # {
            #     "waitResponse": true,
            #     "messageId": "kkkss8fepn-1756665973142-bptyoj06z",
            #     "deviceId": "Instance-a92c5505-ccdb-4ac7-b0fe-74f4fa5fc5b9",
            #     "command": "Update",
            #     "payload": {
            #         "source": "web-client",
            #         "app": "leaf-fc"
            #     },
            #     "timestamp": "2025-08-31T18:46:13.142Z"
            # }

            self._message_buffer.append(message)

    def _process_message_in_worker(self, message: MQTTMessage):
        """Process a message in the worker thread context."""
        try:
            topic = message.topic
            payload = message.payload
            
            self.log.debug(f"Processing MQTT message on topic: {topic}")

            # Process direct topic subscriptions
            if topic in self._subscriptions:
                callback = self._subscriptions[topic]
                self._invoke_callback_safely(callback, topic, payload)

            # Process pattern subscriptions
            for pattern, callback in self._subscription_patterns.items():
                if self._topic_matches_pattern(topic, pattern):
                    self._invoke_callback_safely(callback, topic, payload)

            # Process handlers (similar to MavlinkExternalProxy)
            handlers = self._handlers.get(topic, [])
            for handler in handlers:
                self._invoke_callback_safely(handler, topic, payload)

        except Exception as e:
            self.log.error(f"Error processing message in worker: {e}")

    def _invoke_callback_safely(self, callback: Callable, topic: str, payload: Dict[str, Any]):
        """Safely invoke a callback, handling both sync and async functions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                # Async callback - schedule it on the event loop
                if self._loop and not self._loop.is_closed():
                    asyncio.run_coroutine_threadsafe(
                        callback(topic, payload), 
                        self._loop
                    )
                else:
                    self.log.warning(f"Cannot invoke async callback for {topic}: event loop not available")
            else:
                # Sync callback - call directly in worker thread
                callback(topic, payload)
                
        except Exception as e:
            self.log.error(f"Error in callback for topic {topic}: {e}")

    # ------ Handler Registration (MavlinkExternalProxy-style) ------ #

    def register_handler(self, topic: str, handler: Callable[[str, Dict[str, Any]], None]):
        """Register a handler for a specific topic (similar to MavlinkExternalProxy pattern)."""
        self._handlers[topic].append(handler)
        self.log.debug(f"Registered handler for topic: {topic}")

    def unregister_handler(self, topic: str, handler: Callable[[str, Dict[str, Any]], None]):
        """Unregister a handler for a specific topic."""
        if topic in self._handlers:
            try:
                self._handlers[topic].remove(handler)
                if not self._handlers[topic]:
                    del self._handlers[topic]
                self.log.debug(f"Unregistered handler for topic: {topic}")
            except ValueError:
                self.log.warning(f"Handler not found for topic: {topic}")

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
        """Setup FastAPI callback server for receiving messages (lightweight - only enqueues)."""
        if not self.enable_callbacks:
            return

        self.callback_app = FastAPI(title="MQTT Callback Server")

        @self.callback_app.post('/callback')
        async def message_callback(message: MessageCallback):
            """Handle incoming MQTT messages - lightweight enqueue only."""
            try:
                # Create internal message object and enqueue it
                mqtt_message = MQTTMessage(
                    topic=message.topic,
                    payload=message.payload,
                    timestamp=message.timestamp,
                    qos=message.qos
                )
                
                # Enqueue for worker thread processing
                self._enqueue_message(mqtt_message)
                
                return {"status": "success", "queued": True}
            except Exception as e:
                self.log.error(f"Error enqueuing callback message: {e}")
                return {"status": "error", "message": str(e)}

        @self.callback_app.get('/health')
        async def callback_health():
            """Health check for callback server."""
            buffer_size = len(self._message_buffer) if hasattr(self, '_message_buffer') else 0
            return {
                "status": "healthy", 
                "timestamp": datetime.now().isoformat(),
                "buffer_size": buffer_size,
                "worker_threads": len(self._worker_threads),
                "worker_running": self._worker_running.is_set() if hasattr(self, '_worker_running') else False
            }

        @self.callback_app.get('/stats')
        async def callback_stats():
            """Statistics for callback server and message processing."""
            return {
                "buffer_size": len(self._message_buffer) if hasattr(self, '_message_buffer') else 0,
                "max_buffer_size": self.max_message_buffer,
                "worker_threads": len(self._worker_threads),
                "subscriptions": len(self._subscriptions),
                "patterns": len(self._subscription_patterns),
                "handlers": sum(len(handlers) for handlers in self._handlers.values()),
                "worker_running": self._worker_running.is_set() if hasattr(self, '_worker_running') else False
            }

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
        # Get organization ID on-demand
        organization_id = self._get_organization_id()
        
        if not organization_id or not self.device_id:
            self.log.warning("Cannot subscribe to device topics: missing org or device ID")
            return

        # Default topics to subscribe to
        topics = [
            f"org/{organization_id}/device/{self.device_id}/command/edge",
            f"org/{organization_id}/device/{self.device_id}/response",
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
        """Check MQTT proxy health status with buffer statistics."""
        buffer_size = 0
        with self._buffer_lock:
            buffer_size = len(self._message_buffer)
        
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
                "enable_callbacks": self.enable_callbacks,
                "max_message_buffer": self.max_message_buffer,
                "worker_threads": self.worker_threads,
                "worker_sleep_ms": self.worker_sleep_ms
            },
            "message_processing": {
                "buffer_size": buffer_size,
                "buffer_utilization": buffer_size / self.max_message_buffer if self.max_message_buffer > 0 else 0,
                "worker_threads_active": len(self._worker_threads),
                "worker_running": self._worker_running.is_set()
            },
            "subscriptions": {
                "topics": list(self._subscriptions.keys()),
                "patterns": list(self._subscription_patterns.keys()),
                "handlers": {topic: len(handlers) for topic, handlers in self._handlers.items()}
            },
            "device_info": {
                "organization_id": self._get_organization_id(),
                "robot_instance_id": self.robot_instance_id
            }
        }
        
        return health_status