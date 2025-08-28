from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
import time
import logging

# Import proxy types for type hints
from ..proxies.redis import RedisProxy
from ..proxies.localdb import LocalDBProxy
from ..proxies.external import MavLinkExternalProxy
from ..proxies.cloud import CloudDBProxy
from ..proxies.bucket import S3BucketProxy
from ..proxies.mqtt import MQTTProxy
from ..api import get_proxies

router = APIRouter(tags=["health"])

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the _logger for api endpoints."""
    global _logger
    _logger = logger
    if not isinstance(_logger, logging.Logger):
        raise ValueError("Logger must be an instance of logging.Logger")
    if not _logger.name:
        raise ValueError("Logger must have a name set")
    if not _logger.handlers:
        raise ValueError("Logger must have at least one handler configured")

def get_logger() -> Optional[logging.Logger]:
    """Get the logger instance."""
    global _logger
    if not _logger:
        raise ValueError("Logger has not been set. Call _set_logger first.")
    return _logger

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    logger = get_logger()
    logger.info("Health check requested")
    return {"status": "ok"}

@router.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check endpoint that reports the status of each proxy."""
    proxies = get_proxies()
    logger = get_logger()
    
    if not proxies:
        logger.warning("Health check requested but no proxies are configured.")
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
            logger.error(f"Error checking Redis proxy health: {e}")
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
            logger.error(f"Error checking LocalDB proxy health: {e}")
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
            logger.error(f"Error checking MAVLink proxy health: {e}")
            health_status["proxies"]["ext_mavlink"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check MAVLink proxy status"
            }
            overall_healthy = False
    
    # Check Cloud proxy
    if "cloud" in proxies:
        cloud_proxy: CloudDBProxy = proxies["cloud"]
        try:
            cloud_status = await _check_cloud_proxy(cloud_proxy)
            health_status["proxies"]["cloud"] = cloud_status
            if cloud_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            logger.error(f"Error checking Cloud proxy health: {e}")
            health_status["proxies"]["cloud"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check Cloud proxy status"
            }
            overall_healthy = False
    
    # Check S3 Bucket proxy
    if "bucket" in proxies:
        bucket_proxy: S3BucketProxy = proxies["bucket"]
        try:
            bucket_status = await _check_bucket_proxy(bucket_proxy)
            health_status["proxies"]["bucket"] = bucket_status
            if bucket_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            logger.error(f"Error checking S3 Bucket proxy health: {e}")
            health_status["proxies"]["bucket"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check S3 Bucket proxy status"
            }
            overall_healthy = False
    
    # Check MQTT proxy
    if "mqtt" in proxies:
        mqtt_proxy = proxies["mqtt"]
        try:
            mqtt_status = await _check_mqtt_proxy(mqtt_proxy)
            health_status["proxies"]["mqtt"] = mqtt_status
            if mqtt_status["status"] != "healthy":
                overall_healthy = False
        except Exception as e:
            logger.error(f"Error checking MQTT proxy health: {e}")
            health_status["proxies"]["mqtt"] = {
                "status": "error",
                "error": str(e),
                "details": "Failed to check MQTT proxy status"
            }
            overall_healthy = False
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    return health_status

async def _check_redis_proxy(proxy: RedisProxy) -> Dict[str, Any]:
    """Check Redis proxy health."""
    logger = get_logger()
    try:
        # Check if client is initialized
        if not proxy._client:
            logger.warning("Redis client not initialized")
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
                logger.error(f"Error fetching online applications: {e}")
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
        logger.error(f"Error checking Redis proxy health: {e}")
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
    logger = get_logger()

    try:

        # Basic connection test - try to make a simple request
        test_response = await proxy._get_current_instance()

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
        logger.error(f"Error checking LocalDB proxy health: {e}")
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
    logger = get_logger()
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
        logger.error(f"Error checking MAVLink proxy health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "endpoint": proxy.endpoint,
                "baud": proxy.baud,
                "connected": False
            }
        }

async def _check_cloud_proxy(proxy: CloudDBProxy) -> Dict[str, Any]:
    """Check Cloud proxy health."""
    logger = get_logger()
    try:
        # Test basic connectivity by trying to get access token
        credentials = await proxy._get_access_token()
        
        if credentials and credentials.get('accessToken'):
            status_info = {
                "status": "healthy",
                "connection": {
                    "endpoint": proxy.endpoint,
                    "connected": True
                },
                "authentication": {
                    "credentials_cached": bool(proxy._session_cache.get('credentials')),
                    "credentials_expire_time": proxy._session_cache.get('expires_at', 0)
                },
                "machine_info": {
                    "machine_id": proxy._get_machine_id()
                }
            }
            
            # Test a simple API call if possible
            try:
                # Try to make a test call to verify API connectivity
                test_result = await proxy.scan_items("test_table", [])
                # Even if the table doesn't exist, we should get a structured response
                if isinstance(test_result, dict):
                    status_info["api_test"] = {
                        "connectivity": "ok",
                        "can_make_requests": True
                    }
                else:
                    status_info["api_test"] = {
                        "connectivity": "unknown",
                        "can_make_requests": False
                    }
            except Exception as e:
                status_info["api_test"] = {
                    "connectivity": "error",
                    "error": str(e),
                    "can_make_requests": False
                }
            
            return status_info
        else:
            return {
                "status": "unhealthy",
                "details": "Failed to obtain valid access token",
                "connection": {
                    "endpoint": proxy.endpoint,
                    "connected": False
                },
                "authentication": {
                    "credentials_cached": False,
                    "error": "No valid access token"
                }
            }
            
    except Exception as e:
        logger.error(f"Error checking Cloud proxy health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "endpoint": proxy.endpoint,
                "connected": False
            },
            "authentication": {
                "credentials_cached": False,
                "error": "Authentication check failed"
            }
        }

async def _check_bucket_proxy(proxy: S3BucketProxy) -> Dict[str, Any]:
    """Check S3 Bucket proxy health."""
    logger = get_logger()
    try:
        # Test basic connectivity by getting session credentials
        credentials = await proxy._get_session_credentials()
        
        if credentials:
            status_info = {
                "status": "healthy",
                "connection": {
                    "bucket_name": proxy.bucket_name,
                    "connected": True
                },
                "authentication": {
                    "credentials_cached": bool(proxy._session_cache.get('credentials')),
                    "credentials_expire_time": proxy._session_cache.get('expires_at', 0)
                },
                "configuration": {
                    "upload_prefix": proxy.upload_prefix,
                    "allowed_extensions": list(proxy.ALLOWED_EXTENSIONS),
                    "request_timeout": proxy.request_timeout
                }
            }
            
            # Test S3 connectivity if possible
            try:
                if proxy.s3_client:
                    # Try to list a few objects to test S3 connectivity
                    # This is a minimal operation that tests the connection
                    test_result = await proxy._loop.run_in_executor(
                        proxy._exe,
                        lambda: proxy.s3_client.list_objects_v2(
                            Bucket=proxy.bucket_name,
                            Prefix=proxy.upload_prefix,
                            MaxKeys=1
                        )
                    )
                    
                    status_info["s3_test"] = {
                        "connectivity": "ok",
                        "can_access_bucket": True,
                        "bucket_accessible": True
                    }
                else:
                    status_info["s3_test"] = {
                        "connectivity": "no_client",
                        "can_access_bucket": False,
                        "bucket_accessible": False
                    }
            except Exception as e:
                status_info["s3_test"] = {
                    "connectivity": "error",
                    "error": str(e),
                    "can_access_bucket": False,
                    "bucket_accessible": False
                }
            
            return status_info
        else:
            return {
                "status": "unhealthy",
                "details": "Failed to obtain valid S3 session credentials",
                "connection": {
                    "bucket_name": proxy.bucket_name,
                    "connected": False
                },
                "authentication": {
                    "credentials_cached": False,
                    "error": "No valid session credentials"
                }
            }
            
    except Exception as e:
        logger.error(f"Error checking S3 Bucket proxy health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "bucket_name": proxy.bucket_name,
                "connected": False
            },
            "authentication": {
                "credentials_cached": False,
                "error": "Health check failed"
            }
        }

async def _check_mqtt_proxy(proxy: MQTTProxy) -> Dict[str, Any]:
    """Check MQTT proxy health."""
    logger = get_logger()
    try:
        # Use the proxy's built-in health check method
        health_status = await proxy.health_check()
        
        if health_status.get("status") == "healthy":
            return {
                "status": "healthy",
                "connection": health_status.get("connection", {}),
                "configuration": health_status.get("configuration", {}),
                "subscriptions": health_status.get("subscriptions", {}),
                "device_info": health_status.get("device_info", {})
            }
        else:
            return {
                "status": "unhealthy",
                "details": "MQTT proxy reported unhealthy status",
                "connection": health_status.get("connection", {}),
                "error": "Proxy health check failed"
            }
            
    except Exception as e:
        logger.error(f"Error checking MQTT proxy health: {e}")
        return {
            "status": "error",
            "error": str(e),
            "connection": {
                "ts_client": False,
                "callback_server": False,
                "connected": False
            },
            "details": "Health check failed with exception"
        }