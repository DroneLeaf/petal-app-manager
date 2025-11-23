"""
Pydantic models for Petal App Manager.
"""

from .health import (
    HealthStatus,
    # Proxy-specific health models
    RedisProxyHealth,
    LocalDbProxyHealth,
    MavlinkProxyHealth,
    CloudProxyHealth,
    S3BucketProxyHealth,
    MqttProxyHealth,
    ProxyHealthDetail,
    # General health models
    OrganizationManagerHealth,
    DetailedHealthResponse,
    ServiceHealthInfo,
    HealthMessage,
    BasicHealthResponse,
    OrganizationHealthResponse,
)

from .mqtt import (
    MQTTMessage
)

__all__ = [
    "HealthStatus",
    # Proxy-specific health models
    "RedisProxyHealth",
    "LocalDbProxyHealth", 
    "MavlinkProxyHealth",
    "CloudProxyHealth",
    "S3BucketProxyHealth",
    "MqttProxyHealth",
    "ProxyHealthDetail",
    # General health models
    "OrganizationManagerHealth",
    "DetailedHealthResponse", 
    "ServiceHealthInfo",
    "HealthMessage",
    "BasicHealthResponse",
    "OrganizationHealthResponse",
    # MQTTMessage
    "MQTTMessage",
]