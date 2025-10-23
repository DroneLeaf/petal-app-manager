"""
Pydantic models for health check responses and status validation.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional, Union, ClassVar
from datetime import datetime
import time


class HealthStatus:
    """Health status enumeration constants."""
    
    # Standard health status values
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    ERROR = "error"
    UNKNOWN = "unknown"
    WARNING = "warning"


# ===== Proxy-Specific Health Models =====

class RedisConnectionInfo(BaseModel):
    """Redis connection information."""
    host: str
    port: int
    db: int
    connected: bool

class RedisCommunicationInfo(BaseModel):
    """Redis communication information."""
    app_id: str
    listening: bool
    active_handlers: int
    active_subscriptions: int
    online_applications: Optional[List[str]] = None
    online_applications_error: Optional[str] = None

class RedisProxyHealth(BaseModel):
    """Redis proxy health information."""
    status: str = Field(..., description="Health status of the Redis proxy")
    connection: RedisConnectionInfo
    communication: Optional[RedisCommunicationInfo] = None
    error: Optional[str] = None
    details: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

class LocalDbConnectionInfo(BaseModel):
    """LocalDB connection information."""
    host: str
    port: int
    connected: bool

class LocalDbMachineInfo(BaseModel):
    """LocalDB machine information."""
    machine_id: str
    organization_id: str
    robot_type_id: str

class LocalDbProxyHealth(BaseModel):
    """LocalDB proxy health information."""
    status: str = Field(..., description="Health status of the LocalDB proxy")
    connection: LocalDbConnectionInfo
    machine_info: LocalDbMachineInfo
    error: Optional[str] = None
    details: Optional[str] = None
    test_response: Optional[Dict[str, Any]] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

class MavlinkConnectionInfo(BaseModel):
    """MAVLink connection information."""
    endpoint: str
    baud: int
    connected: bool

class MavlinkHeartbeatInfo(BaseModel):
    """MAVLink heartbeat information."""
    connected: bool
    last_received: float
    seconds_since_last: Optional[float] = None
    timeout_threshold: float

class MavlinkWorkerThreadInfo(BaseModel):
    """MAVLink worker thread information."""
    running: bool
    thread_alive: bool

class MavlinkSystemInfo(BaseModel):
    """MAVLink system information."""
    target_system: int
    target_component: int
    source_system: int
    source_component: int

class MavlinkParserInfo(BaseModel):
    """MAVLink parser information."""
    available: bool
    system_id: Optional[int] = None

class MavlinkMonitoringInfo(BaseModel):
    """MAVLink monitoring information."""
    connection_monitor_active: bool
    heartbeat_task_active: bool

class MavlinkProxyHealth(BaseModel):
    """MAVLink proxy health information."""
    status: str = Field(..., description="Health status of the MAVLink proxy")
    connection: MavlinkConnectionInfo
    px4_heartbeat: MavlinkHeartbeatInfo
    leaf_fc_heartbeat: MavlinkHeartbeatInfo
    worker_thread: MavlinkWorkerThreadInfo
    mavlink_info: Optional[MavlinkSystemInfo] = None
    parser: Optional[MavlinkParserInfo] = None
    monitoring: Optional[MavlinkMonitoringInfo] = None
    error: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

class CloudConnectionInfo(BaseModel):
    """Cloud DB connection information."""
    endpoint: str
    connected: bool

class CloudAuthenticationInfo(BaseModel):
    """Cloud DB authentication information."""
    credentials_cached: bool
    credentials_expire_time: float

class CloudMachineInfo(BaseModel):
    """Cloud DB machine information."""
    machine_id: str

class CloudApiTestInfo(BaseModel):
    """Cloud DB API test information."""
    connectivity: str
    can_make_requests: bool
    error: Optional[str] = None

class CloudProxyHealth(BaseModel):
    """Cloud DB proxy health information."""
    status: str = Field(..., description="Health status of the Cloud DB proxy")
    connection: CloudConnectionInfo
    authentication: CloudAuthenticationInfo
    machine_info: CloudMachineInfo
    api_test: Optional[CloudApiTestInfo] = None
    error: Optional[str] = None
    details: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

class S3ConnectionInfo(BaseModel):
    """S3 Bucket connection information."""
    bucket_name: str
    connected: bool

class S3AuthenticationInfo(BaseModel):
    """S3 Bucket authentication information."""
    credentials_cached: bool
    credentials_expire_time: float

class S3ConfigurationInfo(BaseModel):
    """S3 Bucket configuration information."""
    upload_prefix: str
    allowed_extensions: List[str]
    request_timeout: float

class S3TestInfo(BaseModel):
    """S3 Bucket test information."""
    connectivity: str
    can_access_bucket: bool
    bucket_accessible: bool
    error: Optional[str] = None

class S3BucketProxyHealth(BaseModel):
    """S3 Bucket proxy health information."""
    status: str = Field(..., description="Health status of the S3 Bucket proxy")
    connection: S3ConnectionInfo
    authentication: S3AuthenticationInfo
    configuration: S3ConfigurationInfo
    s3_test: Optional[S3TestInfo] = None
    error: Optional[str] = None
    details: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v

class MqttProxyHealth(BaseModel):
    """MQTT proxy health information."""
    status: str = Field(..., description="Health status of the MQTT proxy")
    connection: Dict[str, Any]
    configuration: Optional[Dict[str, Any]] = None
    subscriptions: Optional[Dict[str, Any]] = None
    device_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v


class OrganizationManagerHealth(BaseModel):
    """Health information for OrganizationManager."""
    
    status: str = Field(..., description="Health status of the organization manager")
    file_path: Optional[str] = None
    file_exists: Optional[bool] = None
    organization_info: Optional[Dict[str, Any]] = None
    monitoring: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    details: Optional[str] = None
    message: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN, HealthStatus.WARNING]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v


# Union type for all proxy health models
ProxyHealthDetail = Union[
    RedisProxyHealth,
    LocalDbProxyHealth, 
    MavlinkProxyHealth,
    CloudProxyHealth,
    S3BucketProxyHealth,
    MqttProxyHealth
]

class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""
    
    status: str = Field(..., description="Overall health status")
    timestamp: float = Field(..., description="Unix timestamp when health was checked")
    organization_manager: OrganizationManagerHealth
    proxies: Dict[str, ProxyHealthDetail] = Field(default_factory=dict)
    message: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        if v <= 0:
            raise ValueError("Timestamp must be positive")
        return v


class ServiceHealthInfo(BaseModel):
    """Health information for a service in the Redis message format."""
    
    title: str = Field(..., description="Human-readable service title")
    component_name: str = Field(..., description="Unique component identifier")
    status: str = Field(..., description="Service health status")
    message: str = Field(..., description="Status message")
    timestamp: str = Field(..., description="ISO timestamp when status was checked")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    @validator('timestamp')
    def validate_timestamp_format(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Timestamp must be a valid ISO format")
        return v


class HealthMessage(BaseModel):
    """Health message model for Redis publishing and unified responses."""
    
    title: str = Field(..., description="Application title")
    component_name: str = Field(..., description="Main component name")
    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="Application version")
    message: str = Field(..., description="Overall status message")
    timestamp: str = Field(..., description="ISO timestamp when status was checked")
    services: List[ServiceHealthInfo] = Field(..., description="List of service health statuses")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.ERROR, HealthStatus.UNKNOWN]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    @validator('timestamp')
    def validate_timestamp_format(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except ValueError:
            raise ValueError("Timestamp must be a valid ISO format")
        return v
    
    @validator('services')
    def validate_services_not_empty(cls, v):
        if not v:
            raise ValueError("Services list cannot be empty")
        return v


class BasicHealthResponse(BaseModel):
    """Basic health check response model."""
    
    status: str = Field(default="ok", description="Basic health status")
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["ok", "error"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v


class OrganizationHealthResponse(BaseModel):
    """Organization health check response model."""
    
    status: str = Field(..., description="Response status")
    timestamp: float = Field(..., description="Unix timestamp when health was checked")  
    organization_manager: OrganizationManagerHealth
    error: Optional[str] = None
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["ok", "error"]
        if v not in valid_statuses:
            raise ValueError(f"Status must be one of: {valid_statuses}")
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        if v <= 0:
            raise ValueError("Timestamp must be positive")
        return v