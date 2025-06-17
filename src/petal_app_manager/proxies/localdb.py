"""
LocalDBProxy
===========

• Provides access to the local DynamoDB instance through the controller dashboard API
• Handles machine ID retrieval and authentication for requests
• Abstracts the HTTP communication details away from petals
• Provides async CRUD operations for DynamoDB tables

This proxy allows petals to interact with DynamoDB without worrying about
the underlying HTTP communication details.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import asyncio
import concurrent.futures
import http.client
import json
import logging
import platform
import subprocess
from pathlib import Path

from .base import BaseProxy

class LocalDBProxy(BaseProxy):
    """
    Proxy for communicating with a local DynamoDB instance through a custom API.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 3000,
        debug: bool = False,
    ):
        self.host = host
        self.port = port
        self.debug = debug
        
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.log = logging.getLogger("LocalDBProxy")
        self._machine_id = None
        self._organization_id = None
        self._robot_type_id = None

    @property
    def machine_id(self) -> Optional[str]:
        """Get the machine ID for this instance."""
        return self._machine_id
    
    @property
    def organization_id(self) -> Optional[str]:
        """Get the organization ID for this instance."""
        return self._organization_id
    
    @property
    def robot_type_id(self) -> Optional[str]:
        """Get the robot type ID for this instance."""
        return self._robot_type_id

    async def start(self):
        """Initialize the connection to the local API service."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing LocalDBProxy connection to %s:%s", self.host, self.port)
        # Get machine ID for use in all requests
        self._machine_id = await self._loop.run_in_executor(
            self._exe, self._get_machine_id
        )
        if not self._machine_id:
            self.log.warning("Failed to get machine ID, some operations may fail")
        else:
            self.log.info("LocalDBProxy initialized with machine ID: %s", self._machine_id)

        current_instance = await self._get_current_instance()
        if current_instance is not None:
            self.log.info("Current robot instance: %s", current_instance)
        else:
            self.log.warning("No current robot instance found")

        # Get machine ID and organization ID
        self._organization_id = current_instance.get("data",{}).get("organization_id", None)
        self._robot_type_id = current_instance.get("data",{}).get("robot_type_id", None)
        if self._organization_id is None or self._robot_type_id is None:
            self.log.warning(
                "Organization ID or Robot Type ID not found in current instance"
            )
        else:
            self.log.info(
                "Organization ID: %s, Robot Type ID: %s",
                self._organization_id,
                self._robot_type_id
            )
        self.log.info("LocalDBProxy started successfully")
        
    async def stop(self):
        """Clean up resources when shutting down."""
        self._exe.shutdown(wait=False)
        self.log.info("LocalDBProxy stopped")
        
    def _get_machine_id(self) -> Optional[str]:
        """Get the machine ID using the machine ID executable."""
        try:
            # Determine architecture
            arch = platform.machine().lower()
            is_arm = "arm" in arch
            
            # Build path to executable
            utils_dir = Path(__file__).parent.parent / "utils"
            machine_id_exe = utils_dir / (
                "machineid_arm" if is_arm else "machineid_x86"
            )
            
            # Check if executable exists
            if not machine_id_exe.exists():
                self.log.error(f"Machine ID executable not found at {machine_id_exe}")
                return None
            
            # Execute and get output
            result = subprocess.run(
                [str(machine_id_exe)], 
                capture_output=True, 
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            self.log.error(f"Failed to get machine ID: {e}")
            return None
        
    def _remote_file_request(self, body: Dict[str, Any], path: str, method: str) -> Any:
        """Make a request to the local API service."""
        try:
            conn = http.client.HTTPConnection(self.host, self.port)
            headers = {'Content-Type': 'application/json'}
            
            body_json = json.dumps(body)
            
            if self.debug:
                self.log.debug(f"Making {method} request to {path} with body: {body}")
            
            conn.request(method, path, body=body_json, headers=headers)
            
            response = conn.getresponse()
            raw_data = b""
            
            # Read all chunks of data from the response
            while chunk := response.read(4096):
                raw_data += chunk
            
            # Close the connection
            conn.close()
            
            # Parse the JSON response
            try:
                data = json.loads(raw_data.decode('utf-8'))
                return {"data": data, "success": True}
            except json.JSONDecodeError as e:
                self.log.error(f"Failed to parse response: {e}")
                return {"error": f"Failed to parse response: {e}"}
                
        except Exception as e:
            self.log.error(f"Request failed: {e}")
            return {"error": f"Request failed: {e}"}

    async def _get_current_instance(self) -> Dict[str, Any]:
        """
        Retrieve the current robot instance data from the local database.
        
        Returns:
            The robot instance data as a dictionary if found, or None if an error occurs
        """
        if not self._machine_id:
            self.log.warning("Machine ID not available, cannot get current instance")
            return None
        
        try:
            return await self.get_item(
                table_name="config-robot_instances",
                partition_key="id",
                partition_value=self._machine_id
            )
        except Exception as e:
            self.log.error(f"Failed to get current instance: {e}")
            return None
            
    # ------ Public API methods ------ #
    
    async def get_item(
        self, 
        table_name: str, 
        partition_key: str, 
        partition_value: str
    ) -> Dict[str, Any]:
        """
        Retrieve a single item from DynamoDB using its partition key.
        
        Args:
            table_name: The DynamoDB table name
            partition_key: Name of the partition key (usually 'id')
            partition_value: Value of the partition key to look up
            
        Returns:
            The item as a dictionary if found, or an error dictionary
        """
        if not self._machine_id:
            return {"error": "Machine ID not available"}
        
        body = {
            "onBoardId": self._machine_id,
            "table_name": table_name,
            "partition_key": partition_key,
            "partition_value": partition_value
        }
        
        path = '/drone/onBoard/config/getData'
        
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._remote_file_request(body, path, 'POST')
        )
    
    async def scan_items(
        self, 
        table_name: str, 
        filters: Optional[List[Dict[str, str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan a DynamoDB table with optional filters.
        
        Args:
            table_name: The DynamoDB table name
            filters: List of filter dictionaries, each with 'filter_key_name' and 'filter_key_value'
            
        Returns:
            List of matching items
        """
        if not self._machine_id:
            return [{"error": "Machine ID not available"}]
        
        body = {
            "table_name": table_name,
            "onBoardId": self._machine_id
        }
        
        if filters:
            body["scanFilter"] = filters
        
        path = '/drone/onBoard/config/scanData'
        
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._remote_file_request(body, path, 'POST')
        )
    
    async def update_item(
        self,
        table_name: str,
        filter_key: str,
        filter_value: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update or insert an item in DynamoDB.
        
        Args:
            table_name: The DynamoDB table name
            filter_key: Name of the key to filter on (usually 'id')
            filter_value: Value of the key to update
            data: The complete item data to update or insert
            
        Returns:
            Response from the update operation
        """
        if not self._machine_id:
            return {"error": "Machine ID not available"}
        
        body = {
            "onBoardId": self._machine_id,
            "table_name": table_name,
            "filter_key": filter_key,
            "filter_value": filter_value,
            "data": data
        }
        
        path = '/drone/onBoard/config/updateData'
        
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._remote_file_request(body, path, 'POST')
        )
    
    async def delete_item(
        self,
        table_name: str,
        filter_key: str,
        filter_value: str
    ) -> Dict[str, Any]:
        """
        Delete an item from DynamoDB.
        
        Args:
            table_name: The DynamoDB table name
            filter_key: Name of the key to filter on (usually 'id')
            filter_value: Value of the key to delete
            
        Returns:
            Response from the delete operation
        """
        if not self._machine_id:
            return {"error": "Machine ID not available"}
        
        body = {
            "onBoardId": self._machine_id,
            "table_name": table_name,
            "filter_key": filter_key,
            "filter_value": filter_value
        }
        
        path = '/drone/onBoard/config/deleteData'
        
        return await self._loop.run_in_executor(
            self._exe, 
            lambda: self._remote_file_request(body, path, 'POST')
        )