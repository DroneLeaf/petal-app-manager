from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
import time
import logging

# Import proxy types for type hints
from ..proxies.redis import RedisProxy
from ..proxies.localdb import LocalDBProxy
from ..proxies.external import MavLinkExternalProxy

router = APIRouter(tags=["health"])

# Global proxy references - these will be set by the main application
_proxies: Dict[str, Any] = {}

def set_proxies(proxies: Dict[str, Any]):
    """Set the proxy instances for health checks."""
    global _proxies
    _proxies = proxies

def get_proxies() -> Dict[str, Any]:
    """Get the proxy instances."""
    return _proxies

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok"}

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check endpoint that reports the status of each proxy."""
    proxies = get_proxies()
    
    if not proxies:
        return {
            "status": "error",
            "message": "No proxies configured",
            "timestamp": time.time()
        }
    
    health_status = {
        "status": "ok",
        "timestamp": time.time(),
        "proxies": {}
    }
    
    overall_healthy = True
    
    # Check Redis proxy
    if "redis" in proxies:
        redis_proxy: RedisProxy = proxies["redis"]
        try:
            redis_status = await _check_redis_proxy(redis_proxy)
            health_status["proxies"]["redis"] = redis_status
            if redis_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            health_status["proxies"]["redis"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check Redis proxy status"
            }
            overall_healthy = False
    
    # Check LocalDB proxy
    if "db" in proxies:
        db_proxy: LocalDBProxy = proxies["db"]
        try:
            db_status = await _check_localdb_proxy(db_proxy)
            health_status["proxies"]["db"] = db_status
            if db_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            health_status["proxies"]["db"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check LocalDB proxy status"
            }
            overall_healthy = False
    
    # Check MAVLink proxy
    if "ext_mavlink" in proxies:
        mavlink_proxy: MavLinkExternalProxy = proxies["ext_mavlink"]
        try:
            mavlink_status = await _check_mavlink_proxy(mavlink_proxy)
            health_status["proxies"]["ext_mavlink"] = mavlink_status
            if mavlink_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            health_status["proxies"]["ext_mavlink"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check MAVLink proxy status"
            }
            overall_healthy = False
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    return health_status

async def _check_redis_proxy(proxy: RedisProxy) -> Dict[str, Any]:
    """Check Redis proxy health."""
    try:
        # Check if client is initialized
        if not proxy._client:
            return {
                "status": "unhealthy",
                "details": "Redis client not initialized",
                "connection": {
                    "host": proxy.host,
                    "port": proxy.port,
                    "db": proxy.db
                }
            }
        
        # Test basic connectivity with ping
        ping_result = await proxy._loop.run_in_executor(
            proxy._exe, 
            proxy._client.ping
        )
        
        if ping_result:
            # Get additional status info
            info = {
                "status": "healthy",
                "connection": {
                    "host": proxy.host,
                    "port": proxy.port,
                    "db": proxy.db,
                    "connected": True
                },
                "communication": {
                    "app_id": proxy.app_id,
                    "listening": proxy._is_listening,
                    "active_handlers": len(proxy._message_handlers),
                    "active_subscriptions": len(proxy._subscription_tasks)
                }
            }
            
            # Try to get online applications
            try:
                online_apps = await proxy.list_online_applications()
                info["communication"]["online_applications"] = online_apps
            except Exception as e:
                info["communication"]["online_applications_error"] = str(e)
            
            return info
        else:
            return {
                "status": "unhealthy",
                "details": "Redis ping failed",
                "connection": {
                    "host": proxy.host,
                    "port": proxy.port,
                    "db": proxy.db,
                    "connected": False
                }
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "host": proxy.host,
                "port": proxy.port,
                "db": proxy.db,
                "connected": False
            }
        }

async def _check_localdb_proxy(proxy: LocalDBProxy) -> Dict[str, Any]:
    """Check LocalDB proxy health."""
    try:
        # Basic connection test - try to make a simple request
        test_response = await proxy._loop.run_in_executor(
            proxy._exe,
            lambda: proxy._remote_file_request(
                {"test": "health_check"}, 
                "/health", 
                "GET"
            )
        )
        
        # Even if the endpoint doesn't exist, we should get a response structure
        # indicating the service is reachable
        connection_ok = "error" in test_response or "data" in test_response
        
        status_info = {
            "status": "healthy" if connection_ok else "unhealthy",
            "connection": {
                "host": proxy.host,
                "port": proxy.port,
                "connected": connection_ok
            },
            "machine_info": {
                "machine_id": proxy.machine_id,
                "organization_id": proxy.organization_id,
                "robot_type_id": proxy.robot_type_id
            }
        }
        
        if not connection_ok:
            status_info["details"] = "Failed to connect to LocalDB service"
            status_info["test_response"] = test_response
            
        return status_info
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "host": proxy.host,
                "port": proxy.port,
                "connected": False
            },
            "machine_info": {
                "machine_id": proxy.machine_id,
                "organization_id": proxy.organization_id,
                "robot_type_id": proxy.robot_type_id
            }
        }

async def _check_mavlink_proxy(proxy: MavLinkExternalProxy) -> Dict[str, Any]:
    """Check MAVLink proxy health."""
    try:
        current_time = time.time()
        
        status_info = {
            "status": "healthy" if proxy.connected else "unhealthy",
            "connection": {
                "endpoint": proxy.endpoint,
                "baud": proxy.baud,
                "connected": proxy.connected
            },
            "heartbeat": {
                "last_received": proxy._last_heartbeat_time,
                "seconds_since_last": current_time - proxy._last_heartbeat_time if proxy._last_heartbeat_time > 0 else None,
                "timeout_threshold": proxy._heartbeat_timeout
            },
            "worker_thread": {
                "running": proxy._running.is_set() if proxy._running else False,
                "thread_alive": proxy._thread.is_alive() if proxy._thread else False
            }
        }
        
        # Add system information if connected
        if proxy.connected and proxy.master:
            status_info["mavlink_info"] = {
                "target_system": proxy.master.target_system,
                "target_component": proxy.master.target_component,
                "source_system": proxy.master.source_system,
                "source_component": proxy.master.source_component
            }
            
            # Add parser status if available
            if hasattr(proxy, '_parser') and proxy._parser:
                status_info["parser"] = {
                    "available": True,
                    "system_id": proxy._parser.system_id
                }
            else:
                status_info["parser"] = {
                    "available": False
                }
        
        # Add monitoring task status
        if hasattr(proxy, '_connection_monitor_task') and proxy._connection_monitor_task:
            status_info["monitoring"] = {
                "connection_monitor_active": not proxy._connection_monitor_task.done(),
                "heartbeat_task_active": hasattr(proxy, '_heartbeat_task') and proxy._heartbeat_task and not proxy._heartbeat_task.done()
            }
        
        return status_info
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "endpoint": proxy.endpoint,
                "baud": proxy.baud,
                "connected": False
            }
        }