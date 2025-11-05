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
import uuid

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
        self.command_edge_topic = "command"
        self.response_topic = "response"
        self.debug_topic = "command"
        self.command_web_topic = "command/web"
        self._handlers: Dict[str, List[Dict[str, str | Callable[[str, Dict[str, Any]], None]]]] = defaultdict(list)

        self.subscribed_topics = set()

        # Connection and worker thread state
        self.is_connected = False
        self._shutdown_flag = False
        self._worker_running = threading.Event()
        self._worker_threads = []
        
        self._device_topics = {}

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
        
        # clear all registered handlers
        self._handlers.clear()

        for topic in self.subscribed_topics:
            await self._unsubscribe_from_topic(topic)

        self.subscribed_topics.clear()

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

    def _get_base_topic(self) -> Optional[str]:
        """
        Get the base topic for this device.
        
        Returns:
            Base topic string if organization_id and device_id are available, None otherwise
        """
        organization_id = self._get_organization_id()
        if not organization_id or not self.device_id:
            self.log.warning("Cannot construct base topic: missing org or device ID")
            return None
        return f"org/{organization_id}/device/{self.device_id}"

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
        """
        Process a single MQTT message in the worker thread.
        Args:
            message: MQTTMessage object to process
        """
        try:
            topic_absolute = message.topic # Extract topic absolute path
            payload = message.payload

            self.log.debug(f"Processing MQTT message on topic: {topic_absolute}")

            # Process topic subscriptions
            if topic_absolute in self.subscribed_topics:
                for handler in self._handlers[topic_absolute]:
                    callback = handler.get("callback")
                    if callback:
                        self._invoke_callback_safely(callback, topic_absolute, payload)
                    else:
                        subscription_id = handler.get("subscription_id")
                        if subscription_id:
                            self.log.debug(f"No callback for topic: {topic_absolute} with subscription ID {subscription_id}")
                        else:
                            self.log.debug(f"No callback for topic: {topic_absolute} with no subscription ID")

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
                "subscriptions": len(self.subscribed_topics),
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

    async def _subscribe_to_topic(self, topic: str) -> bool:
        """
        Subscribe to an MQTT topic via TypeScript client.
        Args:
            topic: Topic to subscribe to (relative to base topic)
        Returns:
            Subscription ID if successful, None otherwise
        """
        try:
            # make sure topic just does not have a leading slash
            if topic.startswith("/"):
                topic = topic[1:]
            
            # Determine full topic to subscribe to
            topic_subscribe = f"{self._get_base_topic()}/{topic}"

            request_data = {
                "topic": topic_subscribe,
                "callbackUrl": self.callback_url if self.enable_callbacks else None
            }
            
            result = await self._make_ts_request("POST", "/subscribe", request_data)
            
            if "error" in result:
                self.log.error(f"Failed to subscribe to {topic_subscribe}: {result['error']}")
                return False


            self.subscribed_topics.add(topic_subscribe)

            self.log.info(f"Subscribed to topic: {topic_subscribe}")
            return True
            
        except Exception as e:
            self.log.error(f"Error subscribing to {topic_subscribe}: {e}")
            return False

    async def _unsubscribe_from_topic(self, topic: str) -> bool:
        """
        Unsubscribe from an MQTT topic.
        Args:
            topic: Topic to unsubscribe from (relative to base topic)
        Returns:
            True if unsubscribed successfully, False otherwise
        """
        try:
            # make sure topic just does not have a leading slash
            if topic.startswith("/"):
                topic = topic[1:]

            topic_unsubscribe = f"{self._get_base_topic()}/{topic}"

            # Unsubscribe using the subscription ID
            if topic_unsubscribe in self.subscribed_topics:
                self.subscribed_topics.remove(topic_unsubscribe)

            self.log.info(f"Unsubscribed from topic: {topic_unsubscribe}")
            return True
            
        except Exception as e:
            self.log.error(f"Error unsubscribing from {topic_unsubscribe}: {e}")
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
            self.command_edge_topic,
            self.response_topic,
            self.debug_topic
        ]

        for topic in topics:
            success = await self._subscribe_to_topic(topic)
            self.register_handler(self._default_message_handler)
            if success:
                self.log.info(f"Auto-subscribed to device topic: {topic}")
            else:
                self.log.error(f"Failed to auto-subscribe to device topic: {topic}")

    async def _default_message_handler(self, topic: str, payload: Dict[str, Any]):
        """Default message handler for device topics."""

        self.log.info(f"Received message on {topic}: {payload}")
        
        # Handle command messages
        # await self._process_command(topic, payload)
        
    async def _process_command(self, topic: str, payload: Dict[str, Any]):
        """Enhanced command processing."""
        command_type = payload.get('command')
        message_id = payload.get('messageId', 'unknown')

        # Log command for audit
        self.log.info(f"Processing command: {payload}")

        # Send response back
        await self.send_command_response(message_id, {
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        })

    async def _publish_message(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> bool:
        """
        Publish a message to an MQTT topic via TypeScript client.
        Args:
            topic: The MQTT topic to publish to
            payload: Message payload as a dictionary
            qos: Quality of Service level (0, 1, or 2)
        Returns:
            True if published successfully, False otherwise
        """

        if not self.is_connected:
            self.log.error("MQTT proxy is not connected")
            return False
        
        # Topic is already the full topic path
        topic_publish = topic

        payload["deviceId"] = self.device_id

        try:
            request_data = {
                "topic": topic_publish,
                "payload": payload,
                "qos": qos,
                "callbackUrl": self.callback_url
            }
            
            result = await self._make_ts_request("POST", "/publish", request_data)
            
            if "error" in result:
                self.log.error(f"Failed to publish message to {topic_publish}: {result['error']}")
                return False
            
            self.log.debug(f"Published message to topic: {topic_publish}")
            return True
            
        except Exception as e:
            self.log.error(f"Error publishing message to {topic_publish}: {e}")
            return False

            return False

    # ------ Public API methods ------ #
    
    async def publish_message(self, payload: Dict[str, Any], qos: int = 1) -> bool:
        """
        Publish a message to an MQTT topic via TypeScript client to 'command/web' topic.
        Args:
            payload: Message payload as a dictionary
            qos: Quality of Service level (0, 1, or 2)
        Returns:
            True if published successfully, False otherwise
        """

        return await self._publish_message(
            topic=f"{self._get_base_topic()}/{self.command_web_topic}",
            payload=payload,
            qos=qos
        )

    async def send_command_response(self, message_id: str, response_data: Dict[str, Any]) -> bool:
        """
        Send a command response to the response topic.
        Args:
            message_id: Original message ID to correlate response
            response_data: Response payload data
        Returns:
            True if published successfully, False otherwise
        """
        response_topic = f"{self._get_base_topic()}/{self.response_topic}"

        response_payload = {
            'messageId': message_id,
            'timestamp': datetime.now().isoformat(),
            **response_data
        }
        
        return await self._publish_message(response_topic, response_payload)

    def register_handler(self, handler: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> str:
        """
        Register a handler to the 'command/edge' topic.
        Args:
            handler: Async callback function to handle messages
        """
        topic_subscribe = f"{self._get_base_topic()}/{self.command_edge_topic}"

        # ensure topic is subscribed
        if topic_subscribe not in self.subscribed_topics:
            self.log.error(f"Cannot register handler: not subscribed to topic {topic_subscribe}")
            return None

        # Store callback
        subscription_id = str(uuid.uuid4())
        self._handlers[topic_subscribe].append({
            "callback": handler,
            "subscription_id": subscription_id
        })

        self.log.debug(f"Registered handler for topic: {self.command_edge_topic} with subscription ID: {subscription_id}")
        return subscription_id

    def unregister_handler(self, subscription_id: str) -> bool:
        """
        Unregister a handler from the 'command/edge' topic.
        """
        topic_unsubscribe = f"{self._get_base_topic()}/{self.command_edge_topic}"

        if topic_unsubscribe in self._handlers:
            handlers = self._handlers[topic_unsubscribe]
            for handler in handlers:
                if handler.get("subscription_id") == subscription_id:
                    handlers.remove(handler)
                    self.log.debug(f"Unregistered handler for topic: {self.command_edge_topic} with subscription ID: {subscription_id}")
                    return True
                else:
                    self.log.debug(f"No matching handler found for subscription ID: {subscription_id} on topic: {self.command_edge_topic}")
        else:
            self.log.warning(f"No handlers registered for topic: {self.command_edge_topic}")
        return False

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
                "topics": list(self.subscribed_topics),
                "handlers": {topic: len(handlers) for topic, handlers in self._handlers.items()}
            },
            "device_info": {
                "organization_id": self._get_organization_id(),
                "robot_instance_id": self.robot_instance_id
            }
        }
        
        return health_status