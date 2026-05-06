"""
MQTTProxy
=========

• Provides access to AWS IoT MQTT broker through TypeScript client API calls
• Handles callback server for receiving continuous message streams
• Uses async callback dispatch for message processing
• Abstracts MQTT communication details away from petals
• Provides async pub/sub operations with callback-style message handling

This proxy allows petals to interact with MQTT without worrying about
the underlying connection management and HTTP communication details.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Callable, Awaitable
from collections import deque, defaultdict
import asyncio
import concurrent.futures
import json
import logging
import os
from datetime import datetime
import functools
import uuid

import requests
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel

from .base import BaseProxy
from ..organization_manager import get_organization_manager

class MessageCallback(BaseModel):
    """Model for incoming MQTT messages via callback"""
    topic: str
    payload: Dict[str, Any]
    timestamp: Optional[str] = None
    qos: Optional[int] = None

class MQTTProxy(BaseProxy):
    """
    Proxy for communicating with AWS IoT MQTT through TypeScript client API calls.
    Uses async callback dispatch for message processing.
    
    The callback endpoint is exposed as a FastAPI router that should be registered
    with the main application. The callback_port should be set to the main app's port
    (e.g., 8000) since the callback router is now part of the main app.
    
    Configuration note:
        Set PETAL_CALLBACK_PORT to the main FastAPI app port (default: 8000)
        The callback URL will be: http://{callback_host}:{callback_port}/mqtt-callback/callback
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
        max_seen_message_ids: int = 1000,
        command_edge_topic: str = "command/edge",
        response_topic: str = "response",
        test_topic: str = "command",
        command_web_topic: str = "command/web",
        health_check_interval: float = 10.0,
        health_probe_timeout_s: float = 2.0,
    ):
        self.ts_client_host = ts_client_host
        self.ts_client_port = ts_client_port
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.enable_callbacks = enable_callbacks
        self.debug = debug
        self.request_timeout = request_timeout
        
        # For HTTP callback router (registered with main FastAPI app)
        self.callback_router: Optional[APIRouter] = None  # Router to be registered with main app
        
        # Base URL for TypeScript client
        self.ts_base_url = f"http://{self.ts_client_host}:{self.ts_client_port}"
        # Callback URL now points to the main app's router endpoint (not a separate server)
        # The callback_port should be the main FastAPI app port
        self.callback_url = f"http://{self.callback_host}:{self.callback_port}/mqtt-callback/callback" if self.enable_callbacks else None
        
        # Duplicate message filtering
        self._seen_message_ids = deque(maxlen=max_seen_message_ids)
        
        # Subscription management
        self.command_edge_topic = command_edge_topic
        self.response_topic = response_topic
        self.ack_topic = "ack"
        self.test_topic = test_topic
        self.command_web_topic = command_web_topic
        self._handlers: Dict[str, List[Dict[str, str | Callable[[str, Dict[str, Any]], None]]]] = defaultdict(list)

        self.subscribed_topics = set()

        # Connection state
        self.is_connected = False
        self._shutdown_flag = False
        
        self._device_topics = {}
        
        # Health monitoring
        self._health_monitor_task = None
        self._health_check_interval = health_check_interval
        self._health_probe_timeout_s = health_probe_timeout_s

        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="MQTTProxy")
        self.log = logging.getLogger("MQTTProxy")
        
        # Setup callback router in __init__ so it's available for registration with main app
        # before start() is called
        if self.enable_callbacks:
            self._setup_callback_router()

    async def start(self):
        """Initialize the MQTT proxy and start callback processing."""
        
        # Get robot instance ID for basic setup
        self.robot_instance_id = self._get_machine_id()
        self.device_id = f"Instance-{self.robot_instance_id}" if self.robot_instance_id else None

        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing MQTTProxy connection")
        
        # Validate basic configuration (organization_id will be fetched on-demand)
        if not self.device_id:
            self.log.error("Robot Instance ID must be available from OrganizationManager")
            self.log.warning("MQTTProxy will remain inactive until Robot Instance ID is available")
            return
        
        try:
            # Note: callback_router is already set up in __init__ for early registration
            # with the main app before start() is called
            
            # Check TypeScript client health
            is_healthy = await self._check_ts_client_health()
            
            if is_healthy:
                self.log.info("TypeScript MQTT client is healthy")
                # Try to subscribe to default device topics if organization ID is available.
                # NOTE: ``/health`` returning 200 does NOT guarantee the TS
                # sidecar's broker connection is established — it can return
                # 200 a few hundred ms before the AWS-IoT MQTT session is
                # actually up, in which case our /subscribe RPC succeeds at
                # the HTTP layer but the broker silently drops the
                # subscription.  We therefore mark ``is_connected`` only
                # once :meth:`_ensure_subscriptions` reports convergence;
                # if the first pass doesn't converge, the health monitor
                # below will keep retrying every health-check interval
                # until the TS sidecar fully accepts every expected topic.
                organization_id = self._get_organization_id()
                if organization_id:
                    self.log.info("Organization ID available, subscribing to device topics...")
                    try:
                        from .. import Config
                        await asyncio.wait_for(
                            self._ensure_subscriptions(),
                            timeout=Config.MQTT_SUBSCRIBE_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        self.log.warning(
                            "Timeout subscribing to device topics during startup; "
                            "health monitor will keep retrying."
                        )
                    except Exception as e:
                        self.log.error(
                            f"Failed to subscribe to device topics during startup: {e}; "
                            f"health monitor will keep retrying."
                        )
                    # Reflect actual subscription state, not optimistic.
                    self.is_connected = (
                        len(
                            [t for t in self._expected_device_topics()
                             if t not in self.subscribed_topics]
                        ) == 0
                    )
                    if self.is_connected:
                        self.log.info("Successfully subscribed to all device topics")
                    else:
                        self.log.warning(
                            "Initial subscribe did not fully converge "
                            "(TS sidecar may still be connecting to broker); "
                            "health monitor will keep retrying every %.1fs.",
                            self._health_check_interval,
                        )
                else:
                    self.log.info(
                        "Organization ID not available; deferring device topic "
                        "subscription. Health monitor will subscribe once org_id arrives."
                    )
                    self.is_connected = False
            else:
                self.log.warning("TypeScript MQTT client is not accessible - will monitor and retry")
                self.is_connected = False

            # Always start health monitoring task to detect connectivity restoration
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
            self.log.info("MQTTProxy started with health monitoring")
            
        except Exception as e:
            self.log.error(f"Failed to initialize MQTTProxy: {e}")
            self.log.warning("MQTTProxy connection failed - will monitor and retry")
            self.is_connected = False
            # Still start health monitor to detect when things recover
            self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())
        
    async def stop(self):
        """Clean up resources when shutting down."""
        self.log.info("Stopping MQTTProxy...")
        
        # Cancel health monitor task
        if self._health_monitor_task and not self._health_monitor_task.done():
            self._health_monitor_task.cancel()
            try:
                await self._health_monitor_task
            except asyncio.CancelledError:
                pass
        
        # clear all registered handlers
        self._handlers.clear()

        for topic in list(self.subscribed_topics):
            await self._unsubscribe_from_topic(topic)

        self.subscribed_topics.clear()

        # Set shutdown flag
        self._shutdown_flag = True
        self.is_connected = False
        
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
    
    # ------ Message Processing ------ #

    def _process_incoming_message(self, topic: str, payload: Dict[str, Any]):
        """
        Process an incoming MQTT message - dedup and dispatch to handlers.
        Called directly from the HTTP callback handler.
        """
        try:
            # Duplicate check by messageId
            msg_id = payload.get("messageId")
            if msg_id:
                if msg_id in self._seen_message_ids:
                    self.log.debug(f"Duplicate message detected, skipping: {msg_id}")
                    return
                self._seen_message_ids.append(msg_id)

            self.log.debug(f"Processing MQTT message on topic: {topic}")

            # Dispatch to registered handlers
            if topic in self.subscribed_topics:
                for handler in self._handlers[topic]:
                    callback = handler.get("callback")
                    is_cpu_heavy = handler.get("cpu_heavy", False)
                    if callback:
                        self._invoke_callback_safely(callback, topic, payload, cpu_heavy=is_cpu_heavy)
                    else:
                        subscription_id = handler.get("subscription_id")
                        if subscription_id:
                            self.log.debug(f"No callback for topic: {topic} with subscription ID {subscription_id}")
                        else:
                            self.log.debug(f"No callback for topic: {topic} with no subscription ID")
            else:
                self.log.debug(f"Received message for unsubscribed topic: {topic}")

        except Exception as e:
            self.log.error(f"Error processing incoming message: {e}")
            
    def _invoke_callback_safely(
        self,
        callback: Callable,
        topic: str,
        payload: Dict[str, Any],
        *,
        cpu_heavy: bool = False,
    ):
        """Safely invoke an async callback by scheduling it on the event loop.
        
        Since MQTT callbacks arrive via FastAPI HTTP handlers (already on the
        event loop), we use create_task() instead of run_coroutine_threadsafe().
        When *cpu_heavy* is ``True`` the coroutine body is executed inside
        ``loop.run_in_executor`` to avoid blocking the event loop.
        """
        try:
            if self._loop and not self._loop.is_closed():
                if cpu_heavy:
                    async def _offloaded():
                        await self._loop.run_in_executor(
                            self._exe, lambda: asyncio.run(callback(topic, payload))
                        )
                    self._loop.create_task(_offloaded())
                else:
                    self._loop.create_task(callback(topic, payload))
            else:
                self.log.warning(f"Cannot invoke async callback for {topic}: event loop not available")
        except Exception as e:
            self.log.error(f"Error in callback for topic {topic}: {e}")

    # ------ TypeScript Client Communication ------ #

    async def _check_ts_client_health(self) -> bool:
        """Check if TypeScript MQTT client is healthy.

        Uses the per-instance ``_health_probe_timeout_s`` (configured via
        ``Config.MQTT_HEALTH_PROBE_TIMEOUT_S``) so a hung sidecar cannot
        block the single MQTTProxy executor thread for the full
        ``request_timeout`` (30 s) and starve subscribe/publish RPCs.
        """
        try:
            response = await self._loop.run_in_executor(
                self._exe,
                lambda: requests.get(
                    f"{self.ts_base_url}/health",
                    timeout=self._health_probe_timeout_s,
                ),
            )
            return response.status_code == 200
        except Exception as e:
            self.log.debug(f"TypeScript client unreachable: {type(e).__name__}")
            return False

    def _expected_device_topics(self) -> List[str]:
        """Return the fully-qualified set of device topics this proxy
        expects to be subscribed to whenever TS+org are both available."""
        base_topic = self._get_base_topic()
        if not base_topic:
            return []
        return [
            f"{base_topic}/{self.command_edge_topic}",
            f"{base_topic}/{self.response_topic}",
            f"{base_topic}/{self.test_topic}",
        ]

    async def _ensure_subscriptions(self) -> bool:
        """Re-subscribe to any expected device topics that aren't already in
        ``self.subscribed_topics``.  Returns True iff every expected topic
        is subscribed at the end of the call.

        This is the single place that drives convergence between
        "what we want" (``_expected_device_topics``) and "what the TS
        sidecar has accepted" (``self.subscribed_topics``).  It is
        invoked on every healthy poll of the health monitor so that a
        startup race (TS ``/health`` returns 200 before its broker
        connection finishes — silently dropping our subscribe RPC), a
        late-arriving org_id, or a silent broker flap all self-heal.
        """
        expected = self._expected_device_topics()
        if not expected:
            # No org_id / device_id yet; nothing to do.
            return False

        base_topic = self._get_base_topic()
        missing = [t for t in expected if t not in self.subscribed_topics]
        if not missing:
            return True

        self.log.info(
            "Re-subscribing to %d/%d missing device topics...",
            len(missing), len(expected),
        )
        for topic in missing:
            relative = topic[len(base_topic) + 1:] if topic.startswith(base_topic + "/") else topic
            ok = await self._subscribe_to_topic(relative)
            if not ok:
                self.log.warning(
                    "Subscribe failed for %s; will retry on next health poll.",
                    topic,
                )

        # Register the default device-topic handler once (idempotent),
        # but only after the command_edge topic is actually subscribed —
        # ``register_handler`` refuses to attach to an unsubscribed
        # topic.  We guard against duplicate registrations across
        # reconnects by checking the handler list first.
        cmd_edge_full = f"{base_topic}/{self.command_edge_topic}"
        if cmd_edge_full in self.subscribed_topics:
            existing = self._handlers.get(cmd_edge_full, [])
            already_registered = any(
                h.get("callback") is self._default_message_handler for h in existing
            )
            if not already_registered:
                self.register_handler(self._default_message_handler)

        # Re-evaluate after attempts.
        still_missing = [t for t in expected if t not in self.subscribed_topics]
        if still_missing:
            self.log.warning(
                "After re-subscribe pass, %d/%d device topics still missing; "
                "will retry on next health poll.",
                len(still_missing), len(expected),
            )
            return False

        self.log.info("All device topic subscriptions converged.")
        return True

    async def _health_monitor_loop(self):
        """Periodically poll the TypeScript MQTT sidecar's health and
        keep our device-topic subscriptions converged with what the
        sidecar accepts.

        On every iteration:
          * If the sidecar is unhealthy, mark disconnected and clear our
            local subscription view (so the next recovery re-subscribes
            to every expected topic instead of believing it's still
            subscribed).
          * If the sidecar is healthy, drive
            :meth:`_ensure_subscriptions` to convergence — this handles
            the startup race where ``/health`` is 200 but the sidecar's
            broker connection isn't ready yet (silently dropped subs),
            late-arriving org_id, and any broker flap that doesn't
            also flip ``/health`` to non-200.
        """
        self.log.info("Health monitor started")

        while not self._shutdown_flag:
            try:
                await asyncio.sleep(self._health_check_interval)

                is_healthy = await self._check_ts_client_health()

                if not is_healthy:
                    if self.is_connected or self.subscribed_topics:
                        self.log.warning(
                            "TypeScript client health check failed - marking as disconnected"
                        )
                    self.is_connected = False
                    self.subscribed_topics.clear()
                    continue

                organization_id = self._get_organization_id()
                if not organization_id:
                    # Healthy but org_id not available yet — wait for it.
                    if self.is_connected:
                        self.is_connected = False
                    self.log.info(
                        "TS healthy but organization ID not available yet; "
                        "deferring subscription convergence."
                    )
                    continue

                converged = await self._ensure_subscriptions()
                self.is_connected = converged

            except asyncio.CancelledError:
                self.log.info("Health monitor cancelled")
                break
            except Exception as e:
                self.log.error(f"Error in health monitor loop: {e}")
                # Continue monitoring despite errors

        self.log.info("Health monitor stopped")

    async def _make_ts_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to TypeScript client."""
        try:
            url = f"{self.ts_base_url}{endpoint}"
            
            response = await self._loop.run_in_executor(
                self._exe,
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

    # ------ Callback Router (registered with main FastAPI app) ------ #
    
    def _setup_callback_router(self):
        """Setup FastAPI router for receiving MQTT callback messages.
        
        This router should be registered with the main FastAPI app using:
            app.include_router(mqtt_proxy.callback_router, prefix="/mqtt-callback")
        """
        if not self.enable_callbacks:
            return

        self.callback_router = APIRouter(tags=["MQTT Callback"])
        
        # Store reference to self for use in route handlers
        proxy = self

        @self.callback_router.post('/callback')
        async def message_callback(message: MessageCallback):
            """Handle incoming MQTT messages - dedup and dispatch directly."""
            try:
                proxy._process_incoming_message(message.topic, message.payload)
                return {"status": "success"}
            except Exception as e:
                proxy.log.error(f"Error processing callback message: {e}")
                return {"status": "error", "message": str(e)}

        @self.callback_router.get('/health')
        async def callback_health():
            """Health check for MQTT callback endpoint."""
            return {
                "status": "healthy", 
                "timestamp": datetime.now().isoformat(),
                "subscriptions": len(proxy.subscribed_topics),
            }

        @self.callback_router.get('/stats')
        async def callback_stats():
            """Statistics for MQTT callback and message processing."""
            return {
                "subscriptions": len(proxy.subscribed_topics),
                "handlers": sum(len(handlers) for handlers in proxy._handlers.values()),
            }
        
        self.log.info("MQTT callback router configured (register with main app using include_router)")

    async def _subscribe_to_topic(self, topic: str) -> bool:
        """Subscribe to an MQTT topic via TypeScript client.
        Args:
            topic: Topic to subscribe to (relative to base topic)
        Returns:
            Subscription ID if successful, None otherwise
        """
        try:
            # make sure topic just does not have a leading slash
            if topic.startswith("/"):
                topic = topic[1:]
            
            # Get base topic
            base_topic = self._get_base_topic()
            if not base_topic:
                self.log.error(f"Cannot subscribe to {topic}: base topic not available")
                return False
            
            # Determine full topic to subscribe to
            topic_subscribe = f"{base_topic}/{topic}"

            request_data = {
                "topic": topic_subscribe,
                "callbackUrl": self.callback_url if self.enable_callbacks else None
            }
            
            result = await self._make_ts_request("POST", "/subscribe", request_data)
            self.log.info(f"Subscribe request for {topic_subscribe} returned: {result}")

            if not isinstance(result, dict):
                self.log.error(
                    f"Failed to subscribe to {topic_subscribe}: "
                    f"unexpected response type {type(result).__name__}"
                )
                return False

            if "error" in result:
                self.log.error(f"Failed to subscribe to {topic_subscribe}: {result['error']}")
                return False

            if result.get("success") is not True:
                self.log.warning(
                    f"Subscribe to {topic_subscribe} did not return success=true "
                    f"(broker likely not ready yet); will retry on next health poll. "
                    f"Response: {result}"
                )
                return False

            self.subscribed_topics.add(topic_subscribe)

            self.log.info(f"Subscribed to topic: {topic_subscribe}")
            return True
            
        except Exception as e:
            self.log.error(f"Error subscribing to {topic_subscribe}: {e}")
            return False

    async def _unsubscribe_from_topic(self, topic: str) -> bool:
        """
        Unsubscribe from an MQTT topic on the TypeScript client.

        Accepts either a full topic (``org/<id>/device/<id>/...``) or a
        relative topic (the base prefix is added automatically).  This
        keeps backward compatibility with both calling styles.

        Args:
            topic: Topic to unsubscribe from (full or relative).
        Returns:
            True if the TS client acknowledged the unsubscribe, False otherwise.
        """
        topic_unsubscribe = topic  # default for the except-block log
        try:
            # strip a single leading slash if present
            if topic.startswith("/"):
                topic = topic[1:]

            base_topic = self._get_base_topic()
            if base_topic and topic.startswith(base_topic + "/"):
                topic_unsubscribe = topic
            elif base_topic:
                topic_unsubscribe = f"{base_topic}/{topic}"
            else:
                # No base topic available; trust caller-supplied value.
                topic_unsubscribe = topic

            result = await self._make_ts_request(
                "POST",
                "/unsubscribe",
                {"topic": topic_unsubscribe},
            )

            self.log.info(f"Unsubscribe request for {topic_unsubscribe} returned: {result}")

            if not isinstance(result, dict):
                self.log.error(
                    f"Failed to unsubscribe from {topic_unsubscribe}: "
                    f"unexpected response type {type(result).__name__}"
                )
                return False

            if "error" in result:
                self.log.warning(
                    f"TS client returned error on unsubscribe of {topic_unsubscribe}: "
                    f"{result['error']}"
                )
                return False

            if result.get("success") is not True:
                self.log.warning(
                    f"Unsubscribe of {topic_unsubscribe} did not return success=true; "
                    f"keeping local subscription. Response: {result}"
                )
                return False

            self.subscribed_topics.discard(topic_unsubscribe)
            self.log.info(f"Unsubscribed from topic: {topic_unsubscribe}")
            return True

        except Exception as e:
            self.log.error(f"Error unsubscribing from {topic_unsubscribe}: {e}")
            return False

    async def _subscribe_to_device_topics(self):
        """Subscribe to common device topics automatically."""
        # Get base topic (requires org ID and device ID)
        base_topic = self._get_base_topic()
        
        if not base_topic:
            self.log.warning("Cannot subscribe to device topics: missing org or device ID")
            return
        
        # Default topics to subscribe to
        topics = [
            self.command_edge_topic,
            self.response_topic,
            self.test_topic
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

            if not isinstance(result, dict):
                self.log.error(
                    f"Failed to publish message to {topic_publish}: "
                    f"unexpected response type {type(result).__name__}"
                )
                return False

            if "error" in result:
                self.log.error(f"Failed to publish message to {topic_publish}: {result['error']}")
                return False

            if result.get("success") is not True:
                self.log.error(
                    f"Publish to {topic_publish} did not return success=true; "
                    f"broker likely not ready. Response: {result}"
                )
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

    async def send_command_ack(self, message_id: str, service: str, ack_type: str = 'service-received') -> bool:
        """Send an immediate ACK to confirm command receipt.
        Args:
            message_id: Original message ID to correlate
            service: Name of the service sending the ACK
            ack_type: 'edge-received' (TS client got it) or 'service-received' (petal got it)
        """
        response_topic = f"{self._get_base_topic()}/{self.ack_topic}"
        ack_payload = {
            'messageId': message_id,
            'phase': 'ack',
            'ackType': ack_type,
            'service': service,
            'timestamp': datetime.now().isoformat(),
        }
        return await self._publish_message(response_topic, ack_payload)

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
            'phase': 'result',
            'timestamp': datetime.now().isoformat(),
            **response_data
        }

        return await self._publish_message(response_topic, response_payload)

    def register_handler(
        self,
        handler: Callable[[str, Dict[str, Any]], Awaitable[None]],
        cpu_heavy: bool = False,
    ) -> str:
        """
        Register an async handler to the 'command/edge' topic.
        
        Args:
            handler: Async callback function to handle messages
            cpu_heavy: If True, the handler's CPU-bound work will be offloaded
                to a thread-pool executor managed by the proxy.
            
        Returns:
            Subscription ID string, or None if registration failed
            
        Raises:
            TypeError: If handler is not an async function
        """
        if not asyncio.iscoroutinefunction(handler):
            raise TypeError(
                f"Handler must be an async function (coroutine). "
                f"Got {type(handler).__name__} instead. "
                f"Define your handler with 'async def' instead of 'def'."
            )
        
        topic_subscribe = f"{self._get_base_topic()}/{self.command_edge_topic}"

        # ensure topic is subscribed
        if topic_subscribe not in self.subscribed_topics:
            self.log.error(f"Cannot register handler: not subscribed to topic {topic_subscribe}")
            return None

        # Store callback
        subscription_id = str(uuid.uuid4())
        self._handlers[topic_subscribe].append({
            "callback": handler,
            "subscription_id": subscription_id,
            "cpu_heavy": cpu_heavy,
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
        """Check MQTT proxy health status."""
        health_status = {
            "status": "healthy" if self.is_connected else "unhealthy",
            "connection": {
                "ts_client": await self._check_ts_client_health(),
                "callback_router": self.enable_callbacks and self.callback_router is not None,
                "connected": self.is_connected
            },
            "configuration": {
                "ts_client_host": self.ts_client_host,
                "ts_client_port": self.ts_client_port,
                "callback_host": self.callback_host,
                "callback_port": self.callback_port,
                "enable_callbacks": self.enable_callbacks,
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