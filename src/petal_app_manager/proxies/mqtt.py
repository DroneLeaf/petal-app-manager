"""
CloudDBProxy
============

• Provides access to the cloud DynamoDB instance through authenticated API calls
• Handles authentication token retrieval and management with caching
• Abstracts the HTTP communication details away from petals
• Provides async CRUD operations for DynamoDB tables in the cloud

This proxy allows petals to interact with cloud DynamoDB without worrying about
the underlying authentication and HTTP communication details.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import asyncio
import concurrent.futures
import json
import logging
import time
import os
import http.client
import ssl
from urllib.parse import urlparse

from .base import BaseProxy
from .localdb import LocalDBProxy

class MQTTProxy(BaseProxy):
    """
    Proxy for communicating with a cloud MQTT instance through authenticated API calls.
    """
    
    def __init__(
        self,
        local_db_proxy: LocalDBProxy,
        ts_client_host: str,
        ts_client_port: int,
        callback_host: str,
        callback_port: str,
        enable_callbacks: bool,
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

        # Base URL for TypeScript client
        self.ts_base_url = f"http://{self.ts_client_host}:{self.ts_client_port}"
        self.callback_url = f"http://{self.callback_host}:{self.callback_port}/callback" if self.enable_callbacks else None
        self.organization_id = self._get_organization_id()
        self.robot_instance_id = self._get_machine_id()

        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.log = logging.getLogger("MQTTProxy")

    async def start(self):
        """Initialize the cloud proxy and fetch initial credentials."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing MQTTProxy connection")
        
        # Validate configuration
        if not self.access_token_url or not self.endpoint:
            raise ValueError("ACCESS_TOKEN_URL and CLOUD_ENDPOINT must be configured")
        
        # Fetch initial credentials to validate configuration
        try:
            await self._get_access_token()
            self.log.info("MQTTProxy started successfully")
        except Exception as e:
            self.log.error(f"Failed to initialize MQTTProxy: {e}")
            raise
        
    async def stop(self):
        """Clean up resources when shutting down."""
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

    # ------ Public API methods ------ #

