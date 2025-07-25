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

class CloudDBProxy(BaseProxy):
    """
    Proxy for communicating with a cloud DynamoDB instance through authenticated API calls.
    """
    
    def __init__(
        self,
        access_token_url: str,
        endpoint: str,
        local_db_proxy: LocalDBProxy,
        session_token_url: str = None,
        s3_bucket_name: str = None,
        get_data_url: str = '/drone/onBoard/config/getData',
        scan_data_url: str = '/drone/onBoard/config/scanData',
        update_data_url: str = '/drone/onBoard/config/updateData',
        set_data_url: str = '/drone/onBoard/config/setData',
        debug: bool = False,
        request_timeout: int = 30
    ):
        self.access_token_url = access_token_url
        self.endpoint = endpoint
        self.session_token_url = session_token_url
        self.s3_bucket_name = s3_bucket_name
        self.get_data_url = get_data_url
        self.scan_data_url = scan_data_url
        self.update_data_url = update_data_url
        self.set_data_url = set_data_url
        self.debug = debug
        self.request_timeout = request_timeout
        self.local_db_proxy = local_db_proxy
        
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.log = logging.getLogger("CloudDBProxy")
        
        # Session management
        self._session_cache = {
            'credentials': None,
            'expires_at': 0
        }

    async def start(self):
        """Initialize the cloud proxy and fetch initial credentials."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing CloudDBProxy connection")
        
        # Validate configuration
        if not self.access_token_url or not self.endpoint:
            raise ValueError("ACCESS_TOKEN_URL and CLOUD_ENDPOINT must be configured")
        
        # Fetch initial credentials to validate configuration
        try:
            await self._get_access_token()
            self.log.info("CloudDBProxy started successfully")
        except Exception as e:
            self.log.error(f"Failed to initialize CloudDBProxy: {e}")
            raise
        
    async def stop(self):
        """Clean up resources when shutting down."""
        self._exe.shutdown(wait=False)
        self.log.info("CloudDBProxy stopped")
        
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

    async def _get_access_token(self) -> Dict[str, Any]:
        """
        Fetch AWS session credentials from the session manager with caching.
        
        Returns:
            Dictionary containing access credentials
        """
        current_time = time.time()

        # Check if we have cached credentials that haven't expired
        if (self._session_cache['credentials'] and
            current_time < self._session_cache['expires_at']):
            return self._session_cache['credentials']

        def _fetch_token():
            try:
                self.log.info("Fetching new session credentials")
                
                # Parse the URL to determine connection type
                parsed_url = urlparse(self.access_token_url)
                host = parsed_url.hostname
                port = parsed_url.port
                path = parsed_url.path
                
                # Create appropriate connection
                if parsed_url.scheme == 'https':
                    if port is None:
                        port = 443
                    conn = http.client.HTTPSConnection(host, port, timeout=self.request_timeout)
                else:
                    if port is None:
                        port = 80
                    conn = http.client.HTTPConnection(host, port, timeout=self.request_timeout)
                
                headers = {'Content-Type': 'application/json'}
                
                conn.request('POST', path, headers=headers)
                response = conn.getresponse()
                
                if response.status != 200:
                    try:
                        raise Exception(f"HTTP {response.status}: {response.reason}")
                    except Exception as e:
                        self.log.error(f"Failed to fetch session credentials: {str(e)}")
                        conn.close()
                        return {"error": str(e)}
                raw_data = response.read()
                conn.close()
                
                credentials = json.loads(raw_data.decode('utf-8'))

                # Validate required fields
                required_fields = ['accessToken']
                for field in required_fields:
                    if field not in credentials:
                        raise ValueError(f"Missing required field: {field}")

                # Cache credentials for 50 minutes (assume 1-hour expiry)
                self._session_cache['credentials'] = credentials

                # need to handle expiresAt in time string ('2025-07-24T12:43:20.169Z')
                if 'expiresAt' in credentials:
                    expires_at = credentials['expiresAt']
                    if isinstance(expires_at, str):
                        # Convert ISO 8601 string to timestamp
                        expires_at = time.mktime(time.strptime(expires_at, '%Y-%m-%dT%H:%M:%S.%fZ'))
                    self._session_cache['expires_at'] = expires_at - 600  # Cache for 50 minutes
                else:
                    # Default to 1 hour from now if expiresAt is not provided
                    self._session_cache['expires_at'] = current_time + 3600 - 600

                self.log.info("Session credentials updated successfully")
                return credentials

            except Exception as e:
                self.log.error(f"Failed to fetch session credentials: {str(e)}")
                raise Exception(f"Authentication service error: {str(e)}")

        return await self._loop.run_in_executor(self._exe, _fetch_token)
        
    async def _cloud_request(
        self, 
        body: Dict[str, Any], 
        path: str, 
        method: str = 'POST'
    ) -> Dict[str, Any]:
        """Make an authenticated request to the cloud API service."""
        
        def _make_request():
            try:
                # Get fresh credentials
                credentials = self._session_cache['credentials']
                if not credentials:
                    raise Exception("No valid credentials available")
                
                # Parse the cloud endpoint URL
                parsed_url = urlparse(self.endpoint)
                host = parsed_url.hostname
                port = parsed_url.port
                base_path = parsed_url.path.rstrip('/')
                
                # Create appropriate connection
                if parsed_url.scheme == 'https':
                    if port is None:
                        port = 443
                    conn = http.client.HTTPSConnection(host, port, timeout=self.request_timeout)
                else:
                    if port is None:
                        port = 80
                    conn = http.client.HTTPConnection(host, port, timeout=self.request_timeout)
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {credentials["accessToken"]}'
                }
                
                body_json = json.dumps(body)
                full_path = base_path + path
                
                if self.debug:
                    self.log.debug(f"Making {method} request to {full_path} with body: {body}")
                
                conn.request(method, full_path, body=body_json, headers=headers)
                response = conn.getresponse()
                
                if response.status not in [200, 201]:
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    self.log.error(f"Request failed: {error_msg}")
                    conn.close()
                    return {"error": error_msg}
                
                raw_data = response.read()
                conn.close()
                
                # Parse the JSON response
                try:
                    data = json.loads(raw_data.decode('utf-8'))
                    return {"data": data, "success": True}
                except json.JSONDecodeError as e:
                    self.log.error(f"Failed to parse response: {e}")
                    return {"error": f"Failed to parse response: {e}"}
                    
            except Exception as e:
                self.log.error(f"Unexpected error in cloud request: {e}")
                return {"error": f"Request failed: {e}"}
        
        # Ensure we have valid credentials before making the request
        try:
            await self._get_access_token()
        except Exception as e:
            return {"error": f"Authentication failed: {e}"}
        
        return await self._loop.run_in_executor(self._exe, _make_request)
            
    # ------ Public API methods ------ #
    
    async def get_item(
        self, 
        table_name: str, 
        partition_key: str, 
        partition_value: str,
    ) -> Dict[str, Any]:
        """
        Retrieve a single item from DynamoDB using its partition key.
        Only returns items that are not soft-deleted (deleted != True) and belong to this machine.
        
        Args:
            table_name: The DynamoDB table name
            partition_key: Name of the partition key (usually 'id')
            partition_value: Value of the partition key to look up
            
        Returns:
            The item as a dictionary if found, not deleted, and belongs to this machine, or an error dictionary
        """
        machine_id = self._get_machine_id()

        body = {
            "onBoardId": machine_id,
            "table_name": table_name,
            "partition_key": partition_key,
            "partition_value": partition_value
        }
        
        result = await self._cloud_request(body, self.get_data_url, 'POST')
        
        # Filter out soft-deleted items and items not belonging to this machine
        if result.get("success") and result.get("data"):
            item_data = result["data"]
            if item_data.get("deleted") is True:
                return {"error": "Item not found or has been deleted"}
            # Check if robot_instance_id matches machine_id
            if item_data.get("robot_instance_id") != machine_id:
                return {"error": "Item not found or access denied"}
        
        return result
    
    async def scan_items(
        self, 
        table_name: str, 
        filters: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Scan a DynamoDB table with optional filters.
        Only returns items that are not soft-deleted (deleted != True) and belong to this machine.
        
        Args:
            table_name: The DynamoDB table name
            filters: List of filter dictionaries, each with 'filter_key_name' and 'filter_key_value'
            
        Returns:
            Dictionary containing list of matching items that are not deleted and belong to this machine
        """
        machine_id = self._get_machine_id()

        body = {
            "table_name": table_name,
            "onBoardId": machine_id
        }
        
        # Always add robot_instance_id filter to ensure only this machine's records are returned
        if filters is None:
            filters = []
        else:
            filters = filters.copy()  # Don't modify the original list
        
        # Add robot_instance_id filter
        filters.append({
            "filter_key_name": "robot_instance_id", 
            "filter_key_value": machine_id
        })
        
        body["scanFilter"] = filters

        result = await self._cloud_request(body, self.scan_data_url, 'POST')
        
        # Filter out soft-deleted items and double-check robot_instance_id
        if result.get("success") and result.get("data"):
            if isinstance(result["data"], list):
                # Filter out items where deleted is True or robot_instance_id doesn't match
                filtered_items = [
                    item for item in result["data"] 
                    if (item.get("deleted") is not True and 
                        item.get("robot_instance_id") == machine_id)
                ]
                return {"data": filtered_items, "success": True}
            else:
                # Single item response, check if it's deleted or doesn't belong to this machine
                if (result["data"].get("deleted") is True or 
                    result["data"].get("robot_instance_id") != machine_id):
                    return {"data": [], "success": True}
        
        return result
    
    async def update_item(
        self,
        table_name: str,
        filter_key: str,
        filter_value: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update or insert an item in DynamoDB.
        Automatically adds robot_instance_id to ensure item belongs to this machine.
        
        Args:
            table_name: The DynamoDB table name
            filter_key: Name of the key to filter on (usually 'id')
            filter_value: Value of the key to update
            data: The complete item data to update or insert
            
        Returns:
            Response from the update operation
        """
        # Ensure robot_instance_id is set to machine_id
        machine_id = self._get_machine_id()

        data_with_robot_id = data.copy()
        data_with_robot_id["robot_instance_id"] = machine_id
        
        body = {
            "onBoardId": machine_id,
            "table_name": table_name,
            "filter_key": filter_key,
            "filter_value": filter_value,
            "data": data_with_robot_id
        }

        return await self._cloud_request(body, self.update_data_url, 'POST')
    
    async def set_item(
        self,
        table_name: str,
        filter_key: str,
        filter_value: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Puts an item in DynamoDB.
        Automatically adds robot_instance_id to ensure item belongs to this machine.
        
        Args:
            table_name: The DynamoDB table name
            filter_key: Name of the key to filter on (usually 'id')
            filter_value: Value of the key to update
            data: The complete item data to update or insert
            
        Returns:
            Response from the set operation
        """
        # Ensure robot_instance_id is set to machine_id
        machine_id = self._get_machine_id()

        data_with_robot_id = data.copy()
        data_with_robot_id["robot_instance_id"] = machine_id
        
        body = {
            "onBoardId": machine_id,
            "table_name": table_name,
            "filter_key": filter_key,
            "filter_value": filter_value,
            "data": data_with_robot_id
        }

        return await self._cloud_request(body, self.set_data_url, 'POST')

    async def delete_item(
        self,
        table_name: str,
        filter_key: str,
        filter_value: str,
    ) -> Dict[str, Any]:
        """
        Soft delete an item from DynamoDB by setting deleted=True.
        
        Args:
            table_name: The DynamoDB table name
            filter_key: Name of the key to filter on (usually 'id')
            filter_value: Value of the key to delete
            
        Returns:
            Response from the update operation
        """
        # Get the existing item directly from the database (bypassing soft delete filter)
        machine_id = self._get_machine_id()

        body = {
            "onBoardId": machine_id,
            "table_name": table_name,
            "partition_key": filter_key,
            "partition_value": filter_value
        }

        existing_item_result = await self._cloud_request(body, self.get_data_url, 'POST')
        
        if not existing_item_result.get("success") or not existing_item_result.get("data"):
            return {"error": "Item not found"}
        
        # Update the item with deleted=True while preserving existing data
        item_data = existing_item_result["data"].copy()
        item_data["deleted"] = True
        
        return await self.update_item(
            table_name=table_name,
            filter_key=filter_key,
            filter_value=filter_value,
            data=item_data
        )
