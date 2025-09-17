"""
OrganizationManager
==================

Centralized manager for organization ID and machine ID that monitors the thing-parameters.json file
and provides both organization ID and machine ID to all proxies and petals.

This replaces the previous approach where LocalDBProxy was used to fetch organization ID and machine ID.
Now all components get both IDs from this centralized source.
"""

from __future__ import annotations
import asyncio
import json
import logging
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List, Any
from dataclasses import dataclass

@dataclass
class OrganizationInfo:
    """Organization and machine information extracted from thing-parameters.json and system"""
    organization_id: Optional[str] = None
    machine_id: Optional[str] = None
    thing_name: Optional[str] = None
    retrieved_at: Optional[str] = None
    last_updated: float = 0.0

class OrganizationManager:
    """
    Manages organization ID and machine ID by monitoring the thing-parameters.json file
    and system machine ID.
    
    Features:
    - File watching with periodic polling for organization ID
    - Machine ID detection using system executables
    - Callback notification system when organization ID changes
    - Thread-safe access to organization and machine information
    - Graceful handling of missing/invalid files
    """
    
    def __init__(
        self,
        file_path: str = "/opt/droneleaf/certs/perm/thing-parameters.json",
        poll_interval: float = 5.0,
        startup_timeout: float = 30.0
    ):
        """
        Initialize OrganizationManager.
        
        Args:
            file_path: Path to the thing-parameters.json file
            poll_interval: How often to check the file (seconds)
            startup_timeout: How long to wait for file during startup (seconds)
        """
        self.file_path = Path(file_path)
        self.poll_interval = poll_interval
        self.startup_timeout = startup_timeout
        
        self.log = logging.getLogger("OrganizationManager")
        
        # Organization and machine info with thread-safe access
        self._org_info = OrganizationInfo()
        self._org_lock = threading.RLock()
        
        # Callback management
        self._callbacks: List[Callable[[Optional[str]], None]] = []
        self._callback_lock = threading.Lock()
        
        # File monitoring
        self._last_modified: float = 0.0
        self._last_size: int = 0
        
        # Async task management
        self._monitor_task: Optional[asyncio.Task] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
    async def start(self):
        """Start the organization manager and begin file monitoring."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        
        self.log.info(f"Starting OrganizationManager monitoring {self.file_path}")
        
        # Load machine ID first (this doesn't change)
        await self._load_machine_id()
        
        # Try to load initial organization info
        await self._load_organization_info()
        
        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_file())
        
        self.log.info("OrganizationManager started")
        
    async def stop(self):
        """Stop the organization manager."""
        self._running = False
        
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        self.log.info("OrganizationManager stopped")
    
    @property
    def organization_id(self) -> Optional[str]:
        """Get the current organization ID (thread-safe)."""
        with self._org_lock:
            return self._org_info.organization_id
    
    @property
    def machine_id(self) -> Optional[str]:
        """Get the current machine ID (thread-safe)."""
        with self._org_lock:
            return self._org_info.machine_id
    
    @property
    def organization_info(self) -> OrganizationInfo:
        """Get the current organization info (thread-safe copy)."""
        with self._org_lock:
            return OrganizationInfo(
                organization_id=self._org_info.organization_id,
                machine_id=self._org_info.machine_id,
                thing_name=self._org_info.thing_name,
                retrieved_at=self._org_info.retrieved_at,
                last_updated=self._org_info.last_updated
            )
    
    def register_callback(self, callback: Callable[[Optional[str]], None]):
        """
        Register a callback to be called when organization ID changes.
        
        Args:
            callback: Function that takes organization_id as parameter
        """
        with self._callback_lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)
                self.log.debug(f"Registered organization ID callback: {callback.__name__}")
    
    def unregister_callback(self, callback: Callable[[Optional[str]], None]):
        """
        Unregister a callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        with self._callback_lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
                self.log.debug(f"Unregistered organization ID callback: {callback.__name__}")
    
    async def wait_for_organization_id(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Wait for organization ID to become available.
        
        Args:
            timeout: Maximum time to wait (None for indefinite)
            
        Returns:
            Organization ID when available, or None if timeout
        """
        if timeout is None:
            timeout = self.startup_timeout
            
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            org_id = self.organization_id
            if org_id:
                return org_id
            
            await asyncio.sleep(0.5)
        
        self.log.warning(f"Timed out waiting for organization ID after {timeout}s")
        return None
    
    async def _monitor_file(self):
        """Monitor the thing-parameters.json file for changes."""
        while self._running:
            try:
                await self._check_file_changes()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log.error(f"Error monitoring organization file: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _check_file_changes(self):
        """Check if the file has changed and reload if necessary."""
        try:
            if not self.file_path.exists():
                # File doesn't exist yet - this is expected during startup
                return
            
            stat = self.file_path.stat()
            current_modified = stat.st_mtime
            current_size = stat.st_size
            
            # Check if file has been modified
            if (current_modified != self._last_modified or 
                current_size != self._last_size):
                
                self.log.info("Organization file changed, reloading...")
                await self._load_organization_info()
                
                self._last_modified = current_modified
                self._last_size = current_size
                
        except Exception as e:
            self.log.error(f"Error checking file changes: {e}")
    
    async def _load_organization_info(self):
        """Load organization information from the file."""
        try:
            if not self.file_path.exists():
                self.log.debug(f"Organization file not found at {self.file_path}")
                return
            
            with open(self.file_path, "r") as f:
                data = json.load(f)
            
            # Extract organization ID from multiple possible locations
            org_id = None
            thing_name = None
            retrieved_at = None
            
            # Try thing.lastReported.organizationId first
            if "thing" in data:
                thing_data = data["thing"]
                thing_name = thing_data.get("thingName")
                retrieved_at = thing_data.get("retrievedAt")
                
                if "lastReported" in thing_data:
                    org_id = thing_data["lastReported"].get("organizationId")
            
            # Fallback to shadow.state.reported.organizationId
            if not org_id and "shadow" in data:
                shadow_data = data["shadow"]
                if "state" in shadow_data and "reported" in shadow_data["state"]:
                    org_id = shadow_data["state"]["reported"].get("organizationId")
            
            # Fallback to shadow.state.desired.organizationId
            if not org_id and "shadow" in data:
                shadow_data = data["shadow"]
                if "state" in shadow_data and "desired" in shadow_data["state"]:
                    org_id = shadow_data["state"]["desired"].get("organizationId")
            
            # Update organization info
            old_org_id = None
            with self._org_lock:
                old_org_id = self._org_info.organization_id
                self._org_info.organization_id = org_id
                self._org_info.thing_name = thing_name
                self._org_info.retrieved_at = retrieved_at
                self._org_info.last_updated = time.time()
            
            # Log changes
            if org_id != old_org_id:
                if org_id:
                    self.log.info(f"Organization ID updated: {org_id}")
                else:
                    self.log.warning("Organization ID is no longer available")
                
                # Notify callbacks
                await self._notify_callbacks(org_id)
            
        except json.JSONDecodeError as e:
            self.log.error(f"Invalid JSON in organization file {self.file_path}: {e}")
        except Exception as e:
            self.log.error(f"Error loading organization info from {self.file_path}: {e}")
    
    async def _load_machine_id(self):
        """Load machine ID using the machine ID executable."""
        def _get_machine_id_sync() -> Optional[str]:
            try:
                # Determine architecture
                arch = platform.machine().lower()
                is_arm = "aarch64" in arch
                
                # Build path to executable
                utils_dir = Path(__file__).parent / "utils"
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
        
        try:
            # Run machine ID detection in thread pool
            machine_id = await self._loop.run_in_executor(None, _get_machine_id_sync)
            
            with self._org_lock:
                self._org_info.machine_id = machine_id
            
            if machine_id:
                self.log.info(f"Machine ID loaded: {machine_id}")
            else:
                self.log.warning("Failed to load machine ID")
                
        except Exception as e:
            self.log.error(f"Error loading machine ID: {e}")
    
    async def _notify_callbacks(self, org_id: Optional[str]):
        """Notify all registered callbacks about organization ID change."""
        with self._callback_lock:
            callbacks = self._callbacks.copy()
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(org_id)
                else:
                    # Run sync callback in thread pool to avoid blocking
                    if self._loop:
                        await self._loop.run_in_executor(None, callback, org_id)
                    else:
                        callback(org_id)
            except Exception as e:
                self.log.error(f"Error in organization ID callback {callback.__name__}: {e}")


# Global singleton instance
_organization_manager: Optional[OrganizationManager] = None
_manager_lock = threading.Lock()

def get_organization_manager() -> OrganizationManager:
    """Get the global OrganizationManager instance."""
    global _organization_manager
    
    with _manager_lock:
        if _organization_manager is None:
            _organization_manager = OrganizationManager()
        return _organization_manager

def set_organization_manager(manager: OrganizationManager):
    """Set a custom OrganizationManager instance (for testing)."""
    global _organization_manager
    
    with _manager_lock:
        _organization_manager = manager
