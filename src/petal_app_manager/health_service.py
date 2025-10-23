"""
Unified health check service that eliminates duplication between HTTP endpoints and Redis publishing.
"""

import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import petal_app_manager
from .models.health import (
    DetailedHealthResponse,
    HealthMessage,
    HealthStatus,
    OrganizationManagerHealth,
    ProxyHealthDetail,
    ServiceHealthInfo,
    # Proxy-specific health models
    RedisProxyHealth,
    LocalDbProxyHealth,
    MavlinkProxyHealth,
    CloudProxyHealth,
    S3BucketProxyHealth,
    MqttProxyHealth,
)

# Import proxy types for health checking
from .proxies.redis import RedisProxy
from .proxies.localdb import LocalDBProxy
from .proxies.external import MavLinkExternalProxy
from .proxies.cloud import CloudDBProxy
from .proxies.bucket import S3BucketProxy
from .proxies.mqtt import MQTTProxy
from .organization_manager import get_organization_manager


class HealthService:
    """
    Unified health service that provides consistent health checking functionality
    for both HTTP endpoints and Redis publishing.
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the health service with optional logger."""
        self.logger = logger or logging.getLogger(__name__)
    
    async def get_detailed_health_status(self, proxies_dict: Dict[str, Any]) -> DetailedHealthResponse:
        """
        Get detailed health status for all components.
        
        Args:
            proxies_dict: Dictionary of proxy instances
            
        Returns:
            DetailedHealthResponse: Validated detailed health status
        """
        current_time = time.time()
        overall_healthy = True
        
        # Check OrganizationManager
        org_status = await self._check_organization_manager_safe()
        if org_status.status not in [HealthStatus.HEALTHY]:
            overall_healthy = False
        
        # Check each proxy using internal methods
        proxy_checks = [
            ("redis", self._check_redis_proxy),
            ("db", self._check_localdb_proxy),
            ("ext_mavlink", self._check_mavlink_proxy),
            ("cloud", self._check_cloud_proxy),
            ("bucket", self._check_bucket_proxy),
            ("mqtt", self._check_mqtt_proxy)
        ]
        
        proxies_health = {}
        for proxy_name, check_func in proxy_checks:
            if proxy_name in proxies_dict:
                try:
                    proxy_status = await check_func(proxies_dict[proxy_name])
                    proxies_health[proxy_name] = proxy_status
                    if proxy_status.status not in [HealthStatus.HEALTHY]:
                        overall_healthy = False
                except Exception as e:
                    self.logger.error(f"Error checking {proxy_name} proxy health: {e}")
                    # Create appropriate error model based on proxy type
                    if proxy_name == "redis":
                        from .models.health import RedisConnectionInfo
                        error_proxy = RedisProxyHealth(
                            status=HealthStatus.ERROR,
                            connection=RedisConnectionInfo(host="", port=0, db=0, connected=False),
                            error=str(e),
                            details=f"Failed to check {proxy_name} proxy status"
                        )
                    elif proxy_name == "db":
                        from .models.health import LocalDbConnectionInfo, LocalDbMachineInfo
                        error_proxy = LocalDbProxyHealth(
                            status=HealthStatus.ERROR,
                            connection=LocalDbConnectionInfo(host="", port=0, connected=False),
                            machine_info=LocalDbMachineInfo(machine_id="", organization_id="", robot_type_id=""),
                            error=str(e),
                            details=f"Failed to check {proxy_name} proxy status"
                        )
                    elif proxy_name == "ext_mavlink":
                        from .models.health import (MavlinkConnectionInfo, MavlinkHeartbeatInfo, 
                                                   MavlinkWorkerThreadInfo)
                        error_proxy = MavlinkProxyHealth(
                            status=HealthStatus.ERROR,
                            connection=MavlinkConnectionInfo(endpoint="", baud=0, connected=False),
                            px4_heartbeat=MavlinkHeartbeatInfo(connected=False, last_received=0, timeout_threshold=0),
                            leaf_fc_heartbeat=MavlinkHeartbeatInfo(connected=False, last_received=0, timeout_threshold=0),
                            worker_thread=MavlinkWorkerThreadInfo(running=False, thread_alive=False),
                            error=str(e)
                        )
                    elif proxy_name == "cloud":
                        from .models.health import (CloudConnectionInfo, CloudAuthenticationInfo,
                                                   CloudMachineInfo)
                        error_proxy = CloudProxyHealth(
                            status=HealthStatus.ERROR,
                            connection=CloudConnectionInfo(endpoint="", connected=False),
                            authentication=CloudAuthenticationInfo(credentials_cached=False, credentials_expire_time=0),
                            machine_info=CloudMachineInfo(machine_id=""),
                            error=str(e),
                            details=f"Failed to check {proxy_name} proxy status"
                        )
                    elif proxy_name == "bucket":
                        from .models.health import (S3ConnectionInfo, S3AuthenticationInfo,
                                                   S3ConfigurationInfo)
                        error_proxy = S3BucketProxyHealth(
                            status=HealthStatus.ERROR,
                            connection=S3ConnectionInfo(bucket_name="", connected=False),
                            authentication=S3AuthenticationInfo(credentials_cached=False, credentials_expire_time=0),
                            configuration=S3ConfigurationInfo(upload_prefix="", allowed_extensions=[], request_timeout=0),
                            error=str(e),
                            details=f"Failed to check {proxy_name} proxy status"
                        )
                    elif proxy_name == "mqtt":
                        error_proxy = MqttProxyHealth(
                            status=HealthStatus.ERROR,
                            connection={},
                            error=str(e),
                            details=f"Failed to check {proxy_name} proxy status"
                        )
                    else:
                        # Fallback - shouldn't happen
                        continue
                    
                    proxies_health[proxy_name] = error_proxy
                    overall_healthy = False
        
        overall_status = HealthStatus.HEALTHY if overall_healthy else HealthStatus.UNHEALTHY
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=current_time,
            organization_manager=org_status,
            proxies=proxies_health
        )
    
    async def _check_organization_manager_safe(self) -> OrganizationManagerHealth:
        """Safely check OrganizationManager health with error handling."""
        try:
            org_status_dict = await self._check_organization_manager()
            return OrganizationManagerHealth(**org_status_dict)
        except Exception as e:
            self.logger.error(f"Error checking OrganizationManager health: {e}")
            return OrganizationManagerHealth(
                status=HealthStatus.ERROR,
                error=str(e),
                details="Failed to check OrganizationManager status"
            )
    
    def format_health_message(self, health_data: DetailedHealthResponse) -> HealthMessage:
        """
        Format detailed health data into the Redis message structure.
        
        Args:
            health_data: Detailed health response data
            
        Returns:
            HealthMessage: Validated health message for Redis publishing
        """
        timestamp = datetime.now().isoformat()
        
        # Main status mapping
        main_status = HealthStatus.HEALTHY if health_data.status == HealthStatus.HEALTHY else HealthStatus.UNHEALTHY
        
        # Build services array
        services = []
        
        # Add OrganizationManager service
        org_manager = health_data.organization_manager
        org_status = HealthStatus.HEALTHY if org_manager.status == HealthStatus.HEALTHY else HealthStatus.UNHEALTHY
        org_message = ("Organization management operational" 
                      if org_manager.status == HealthStatus.HEALTHY 
                      else f"Organization manager status: {org_manager.status}")
        
        services.append(ServiceHealthInfo(
            title="Organization Manager",
            component_name="organization_manager",
            status=org_status,
            message=org_message,
            timestamp=timestamp
        ))
        
        # Add proxy services
        proxy_mappings = {
            "redis": {"title": "Redis Proxy", "healthy_msg": "Redis server works"},
            "db": {"title": "LocalDB Proxy", "healthy_msg": "Local database works"},
            "ext_mavlink": {"title": "MAVLink External Proxy", "healthy_msg": "MAVLink server works"},
            "cloud": {"title": "Cloud DB Proxy", "healthy_msg": "Cloud database works"},
            "bucket": {"title": "S3 Bucket Proxy", "healthy_msg": "S3 bucket works"},
            "mqtt": {"title": "MQTT Proxy", "healthy_msg": "MQTT server works"}
        }
        
        for proxy_name, proxy_info in proxy_mappings.items():
            proxy_data = health_data.proxies.get(proxy_name)
            if proxy_data:
                proxy_status = HealthStatus.HEALTHY if proxy_data.status == HealthStatus.HEALTHY else HealthStatus.UNHEALTHY
                
                # Determine message based on status
                if proxy_data.status == HealthStatus.HEALTHY:
                    message = proxy_info["healthy_msg"] 
                elif proxy_data.status == HealthStatus.ERROR:
                    error_msg = proxy_data.error or "Unknown error"
                    message = f"Error: {error_msg}"
                elif proxy_data.status == HealthStatus.UNHEALTHY:
                    details = proxy_data.details or "Service unhealthy"
                    message = f"Unhealthy: {details}"
                else:
                    message = f"Status: {proxy_data.status}"
                
                services.append(ServiceHealthInfo(
                    title=proxy_info["title"],
                    component_name=proxy_name,
                    status=proxy_status,
                    message=message,
                    timestamp=timestamp
                ))
        
        # Create the final health message
        overall_message = "Good conditions" if main_status == HealthStatus.HEALTHY else "Some issues detected"
        
        return HealthMessage(
            title="Petal App Manager",
            component_name="petal_app_manager",
            status=main_status,
            version=petal_app_manager.__version__,
            message=overall_message,
            timestamp=timestamp,
            services=services
        )
    
    async def get_health_message(self, proxies_dict: Dict[str, Any]) -> HealthMessage:
        """
        Get a complete health message suitable for Redis publishing.
        
        Args:
            proxies_dict: Dictionary of proxy instances
            
        Returns:
            HealthMessage: Complete validated health message
        """
        detailed_health = await self.get_detailed_health_status(proxies_dict)
        return self.format_health_message(detailed_health)
    
    # ===== Health Check Helper Methods =====
    
    async def _check_redis_proxy(self, proxy: RedisProxy) -> RedisProxyHealth:
        """Check Redis proxy health."""
        from .models.health import RedisConnectionInfo, RedisCommunicationInfo
        
        try:
            # Check if client is initialized
            if not proxy._client:
                self.logger.warning("Redis client not initialized")
                return RedisProxyHealth(
                    status=HealthStatus.UNHEALTHY,
                    connection=RedisConnectionInfo(
                        host=proxy.host,
                        port=proxy.port,
                        db=proxy.db,
                        connected=False
                    ),
                    details="Redis client not initialized"
                )
            
            # Test basic connectivity with ping
            ping_result = await proxy._loop.run_in_executor(
                proxy._exe, 
                proxy._client.ping
            )
            
            if ping_result:
                # Try to get online applications
                online_apps = None
                online_apps_error = None
                try:
                    online_apps = await proxy.list_online_applications()
                except Exception as e:
                    self.logger.error(f"Error fetching online applications: {e}")
                    online_apps_error = str(e)
                
                return RedisProxyHealth(
                    status=HealthStatus.HEALTHY,
                    connection=RedisConnectionInfo(
                        host=proxy.host,
                        port=proxy.port,
                        db=proxy.db,
                        connected=True
                    ),
                    communication=RedisCommunicationInfo(
                        app_id=proxy.app_id,
                        listening=proxy._is_listening,
                        active_handlers=len(proxy._message_handlers),
                        active_subscriptions=len(proxy._subscription_tasks),
                        online_applications=online_apps,
                        online_applications_error=online_apps_error
                    )
                )
            else:
                return RedisProxyHealth(
                    status=HealthStatus.UNHEALTHY,
                    connection=RedisConnectionInfo(
                        host=proxy.host,
                        port=proxy.port,
                        db=proxy.db,
                        connected=False
                    ),
                    details="Redis ping failed"
                )
        except Exception as e:
            self.logger.error(f"Error checking Redis proxy health: {e}")
            return RedisProxyHealth(
                status=HealthStatus.ERROR,
                connection=RedisConnectionInfo(
                    host=proxy.host,
                    port=proxy.port,
                    db=proxy.db,
                    connected=False
                ),
                error=str(e)
            )

    async def _check_localdb_proxy(self, proxy: LocalDBProxy) -> LocalDbProxyHealth:
        """Check LocalDB proxy health."""
        from .models.health import LocalDbConnectionInfo, LocalDbMachineInfo
        
        try:
            # Basic connection test - try to make a simple request
            test_response = await proxy._get_current_instance()

            # Even if the endpoint doesn't exist, we should get a response structure
            # indicating the service is reachable
            connection_ok = "error" in test_response or "data" in test_response
            
            health_data = LocalDbProxyHealth(
                status=HealthStatus.HEALTHY if connection_ok else HealthStatus.UNHEALTHY,
                connection=LocalDbConnectionInfo(
                    host=proxy.host,
                    port=proxy.port,
                    connected=connection_ok
                ),
                machine_info=LocalDbMachineInfo(
                    machine_id=proxy.machine_id,
                    organization_id=proxy.organization_id,
                    robot_type_id=proxy.robot_type_id
                )
            )
            
            if not connection_ok:
                health_data.details = "Failed to connect to LocalDB service"
                health_data.test_response = test_response
                
            return health_data
            
        except Exception as e:
            self.logger.error(f"Error checking LocalDB proxy health: {e}")
            return LocalDbProxyHealth(
                status=HealthStatus.ERROR,
                connection=LocalDbConnectionInfo(
                    host=proxy.host,
                    port=proxy.port,
                    connected=False
                ),
                machine_info=LocalDbMachineInfo(
                    machine_id=proxy.machine_id,
                    organization_id=proxy.organization_id,
                    robot_type_id=proxy.robot_type_id
                ),
                error=str(e)
            )

    async def _check_mavlink_proxy(self, proxy: MavLinkExternalProxy) -> MavlinkProxyHealth:
        """Check MAVLink proxy health."""
        from .models.health import (MavlinkConnectionInfo, MavlinkHeartbeatInfo, 
                                   MavlinkWorkerThreadInfo, MavlinkSystemInfo,
                                   MavlinkParserInfo, MavlinkMonitoringInfo)
        
        try:
            current_time = time.time()
            
            # System information if connected
            mavlink_info = None
            if proxy.connected and proxy.master:
                mavlink_info = MavlinkSystemInfo(
                    target_system=proxy.master.target_system,
                    target_component=proxy.master.target_component,
                    source_system=proxy.master.source_system,
                    source_component=proxy.master.source_component
                )
            
            # Parser status if available
            parser_info = None
            if proxy.connected and proxy.master:
                if hasattr(proxy, '_parser') and proxy._parser:
                    parser_info = MavlinkParserInfo(
                        available=True,
                        system_id=proxy._parser.system_id
                    )
                else:
                    parser_info = MavlinkParserInfo(available=False)
            
            # Monitoring task status
            monitoring_info = None
            if hasattr(proxy, '_connection_monitor_task') and proxy._connection_monitor_task:
                monitoring_info = MavlinkMonitoringInfo(
                    connection_monitor_active=not proxy._connection_monitor_task.done(),
                    heartbeat_task_active=(hasattr(proxy, '_heartbeat_task') and 
                                         proxy._heartbeat_task and 
                                         not proxy._heartbeat_task.done())
                )
            
            return MavlinkProxyHealth(
                status=HealthStatus.HEALTHY if proxy.connected and proxy.leaf_fc_connected else HealthStatus.UNHEALTHY,
                connection=MavlinkConnectionInfo(
                    endpoint=proxy.endpoint,
                    baud=proxy.baud,
                    connected=proxy.connected
                ),
                px4_heartbeat=MavlinkHeartbeatInfo(
                    connected=proxy.connected,
                    last_received=proxy._last_heartbeat_time,
                    seconds_since_last=(current_time - proxy._last_heartbeat_time 
                                      if proxy._last_heartbeat_time > 0 else None),
                    timeout_threshold=proxy._heartbeat_timeout
                ),
                leaf_fc_heartbeat=MavlinkHeartbeatInfo(
                    connected=proxy.leaf_fc_connected,
                    last_received=proxy._last_leaf_fc_heartbeat_time,
                    seconds_since_last=(current_time - proxy._last_leaf_fc_heartbeat_time 
                                      if proxy._last_leaf_fc_heartbeat_time > 0 else None),
                    timeout_threshold=proxy._leaf_fc_heartbeat_timeout
                ),
                worker_thread=MavlinkWorkerThreadInfo(
                    running=proxy._running.is_set() if proxy._running else False,
                    thread_alive=proxy._thread.is_alive() if proxy._thread else False
                ),
                mavlink_info=mavlink_info,
                parser=parser_info,
                monitoring=monitoring_info
            )
            
        except Exception as e:
            self.logger.error(f"Error checking MAVLink proxy health: {e}")
            return MavlinkProxyHealth(
                status=HealthStatus.ERROR,
                connection=MavlinkConnectionInfo(
                    endpoint=proxy.endpoint,
                    baud=proxy.baud,
                    connected=False
                ),
                px4_heartbeat=MavlinkHeartbeatInfo(
                    connected=False,
                    last_received=0,
                    timeout_threshold=0
                ),
                leaf_fc_heartbeat=MavlinkHeartbeatInfo(
                    connected=False,
                    last_received=0,
                    timeout_threshold=0
                ),
                worker_thread=MavlinkWorkerThreadInfo(
                    running=False,
                    thread_alive=False
                ),
                error=str(e)
            )

    async def _check_cloud_proxy(self, proxy: CloudDBProxy) -> CloudProxyHealth:
        """Check Cloud proxy health."""
        from .models.health import (CloudConnectionInfo, CloudAuthenticationInfo,
                                   CloudMachineInfo, CloudApiTestInfo)
        
        try:
            # Test basic connectivity by trying to get access token
            credentials = await proxy._get_access_token()
            
            if credentials and credentials.get('accessToken'):
                # Test a simple API call if possible
                api_test = None
                try:
                    # Try to make a test call to verify API connectivity
                    test_result = await proxy.scan_items("config-robot_instances", [])
                    # Even if the table doesn't exist, we should get a structured response
                    if isinstance(test_result, dict):
                        api_test = CloudApiTestInfo(
                            connectivity="ok",
                            can_make_requests=True
                        )
                    else:
                        api_test = CloudApiTestInfo(
                            connectivity="unknown",
                            can_make_requests=False
                        )
                except Exception as e:
                    api_test = CloudApiTestInfo(
                        connectivity="error",
                        can_make_requests=False,
                        error=str(e)
                    )
                
                return CloudProxyHealth(
                    status=HealthStatus.HEALTHY,
                    connection=CloudConnectionInfo(
                        endpoint=proxy.endpoint,
                        connected=True
                    ),
                    authentication=CloudAuthenticationInfo(
                        credentials_cached=bool(proxy._session_cache.get('credentials')),
                        credentials_expire_time=proxy._session_cache.get('expires_at', 0)
                    ),
                    machine_info=CloudMachineInfo(
                        machine_id=proxy._get_machine_id()
                    ),
                    api_test=api_test
                )
            else:
                return CloudProxyHealth(
                    status=HealthStatus.UNHEALTHY,
                    connection=CloudConnectionInfo(
                        endpoint=proxy.endpoint,
                        connected=False
                    ),
                    authentication=CloudAuthenticationInfo(
                        credentials_cached=False,
                        credentials_expire_time=0
                    ),
                    machine_info=CloudMachineInfo(machine_id=""),
                    details="Failed to obtain valid access token"
                )
                
        except Exception as e:
            self.logger.error(f"Error checking Cloud proxy health: {e}")
            return CloudProxyHealth(
                status=HealthStatus.ERROR,
                connection=CloudConnectionInfo(
                    endpoint=proxy.endpoint,
                    connected=False
                ),
                authentication=CloudAuthenticationInfo(
                    credentials_cached=False,
                    credentials_expire_time=0
                ),
                machine_info=CloudMachineInfo(machine_id=""),
                error=str(e)
            )

    async def _check_bucket_proxy(self, proxy: S3BucketProxy) -> S3BucketProxyHealth:
        """Check S3 Bucket proxy health."""
        from .models.health import (S3ConnectionInfo, S3AuthenticationInfo,
                                   S3ConfigurationInfo, S3TestInfo)
        
        try:
            # Test basic connectivity by getting session credentials
            credentials = await proxy._get_session_credentials()
            
            if credentials:
                # Test S3 connectivity if possible
                s3_test = None
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
                        
                        s3_test = S3TestInfo(
                            connectivity="ok",
                            can_access_bucket=True,
                            bucket_accessible=True
                        )
                    else:
                        s3_test = S3TestInfo(
                            connectivity="no_client",
                            can_access_bucket=False,
                            bucket_accessible=False
                        )
                except Exception as e:
                    s3_test = S3TestInfo(
                        connectivity="error",
                        can_access_bucket=False,
                        bucket_accessible=False,
                        error=str(e)
                    )
                
                return S3BucketProxyHealth(
                    status=HealthStatus.HEALTHY,
                    connection=S3ConnectionInfo(
                        bucket_name=proxy.bucket_name,
                        connected=True
                    ),
                    authentication=S3AuthenticationInfo(
                        credentials_cached=bool(proxy._session_cache.get('credentials')),
                        credentials_expire_time=proxy._session_cache.get('expires_at', 0)
                    ),
                    configuration=S3ConfigurationInfo(
                        upload_prefix=proxy.upload_prefix,
                        allowed_extensions=list(proxy.ALLOWED_EXTENSIONS),
                        request_timeout=proxy.request_timeout
                    ),
                    s3_test=s3_test
                )
            else:
                return S3BucketProxyHealth(
                    status=HealthStatus.UNHEALTHY,
                    connection=S3ConnectionInfo(
                        bucket_name=proxy.bucket_name,
                        connected=False
                    ),
                    authentication=S3AuthenticationInfo(
                        credentials_cached=False,
                        credentials_expire_time=0
                    ),
                    configuration=S3ConfigurationInfo(
                        upload_prefix=proxy.upload_prefix,
                        allowed_extensions=list(proxy.ALLOWED_EXTENSIONS),
                        request_timeout=proxy.request_timeout
                    ),
                    details="Failed to obtain valid S3 session credentials"
                )
                
        except Exception as e:
            self.logger.error(f"Error checking S3 Bucket proxy health: {e}")
            return S3BucketProxyHealth(
                status=HealthStatus.ERROR,
                connection=S3ConnectionInfo(
                    bucket_name=proxy.bucket_name,
                    connected=False
                ),
                authentication=S3AuthenticationInfo(
                    credentials_cached=False,
                    credentials_expire_time=0
                ),
                configuration=S3ConfigurationInfo(
                    upload_prefix="",
                    allowed_extensions=[],
                    request_timeout=0
                ),
                error=str(e)
            )

    async def _check_mqtt_proxy(self, proxy: MQTTProxy) -> MqttProxyHealth:
        """Check MQTT proxy health."""
        try:
            # Use the proxy's built-in health check method
            health_status = await proxy.health_check()
            
            if health_status.get("status") == "healthy":
                return MqttProxyHealth(
                    status="healthy",
                    connection=health_status.get("connection", {}),
                    configuration=health_status.get("configuration", {}),
                    subscriptions=health_status.get("subscriptions", {}),
                    device_info=health_status.get("device_info", {})
                )
            else:
                return MqttProxyHealth(
                    status="unhealthy",
                    details="MQTT proxy reported unhealthy status",
                    connection=health_status.get("connection", {}),
                    error="Proxy health check failed"
                )
                
        except Exception as e:
            self.logger.error(f"Error checking MQTT proxy health: {e}")
            return MqttProxyHealth(
                status="error",
                error=str(e),
                connection={
                    "ts_client": False,
                    "callback_server": False,
                    "connected": False
                },
                details="Health check failed with exception"
            )

    async def _check_organization_manager(self) -> Dict[str, Any]:
        """Check OrganizationManager health."""
        try:
            org_manager = get_organization_manager()
            org_info = org_manager.organization_info
            
            file_exists = org_manager.file_path.exists() if org_manager.file_path else False
            
            status_info = {
                "status": "healthy" if org_info.organization_id else "warning",
                "file_path": str(org_manager.file_path) if org_manager.file_path else None,
                "file_exists": file_exists,
                "organization_info": {
                    "organization_id": org_info.organization_id,
                    "thing_name": org_info.thing_name,
                    "retrieved_at": org_info.retrieved_at,
                    "last_updated": org_info.last_updated
                },
                "monitoring": {
                    "running": org_manager._running,
                    "poll_interval": org_manager.poll_interval
                }
            }
            
            if not org_info.organization_id:
                status_info["message"] = "Organization ID not yet available from file"
            
            return status_info
            
        except Exception as e:
            self.logger.error(f"Error checking OrganizationManager health: {e}")
            return {
                "status": "error",
                "error": str(e),
                "details": "Failed to check OrganizationManager status"
            }


# Global health service instance
_health_service: Optional[HealthService] = None


def get_health_service(logger: Optional[logging.Logger] = None) -> HealthService:
    """Get or create the global health service instance."""
    global _health_service
    if _health_service is None:
        _health_service = HealthService(logger)
    return _health_service


def set_health_service_logger(logger: logging.Logger) -> None:
    """Set the logger for the global health service."""
    global _health_service
    if _health_service is None:
        _health_service = HealthService(logger)
    else:
        _health_service.logger = logger