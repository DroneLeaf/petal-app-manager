from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

# Import proxy types for type hints
from ..proxies.mqtt import MQTTProxy
from ..api import get_proxies

router = APIRouter(tags=["mqtt"])

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the logger for api endpoints."""
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

# Request models
class PublishMessageRequest(BaseModel):
    topic: str
    payload: Dict[str, Any]
    qos: int = 1

class SubscribeTopicRequest(BaseModel):
    topic: str

class UnsubscribeTopicRequest(BaseModel):
    topic: str

class SubscribePatternRequest(BaseModel):
    pattern: str

# Response models
class MQTTResponse(BaseModel):
    status: str
    message: Optional[str] = None

@router.post(
    "/publish",
    summary="Publish message to MQTT topic",
    description="Publish a message to a specified MQTT topic.",
)
async def publish_message(request: PublishMessageRequest) -> MQTTResponse:
    """Publish a message to an MQTT topic."""
    proxies = get_proxies()
    logger = get_logger()

    if "mqtt" not in proxies:
        logger.error("MQTT proxy not available")
        raise HTTPException(
            status_code=503,
            detail="MQTT proxy not available",
            headers={"source": "publish_message"}
        )

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        success = await mqtt_proxy.publish_message(
            topic=request.topic,
            payload=request.payload,
            qos=request.qos
        )
        
        if success:
            logger.info(f"Published message to topic: {request.topic}")
            return MQTTResponse(status="success", message=f"Message published to {request.topic}")
        else:
            logger.error(f"Failed to publish message to topic: {request.topic}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to publish message to topic: {request.topic}",
                headers={"source": "publish_message"}
            )

    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error publishing message: {str(e)}",
            headers={"source": "publish_message"}
        )

@router.post(
    "/subscribe",
    summary="Subscribe to MQTT topic",
    description="Subscribe to a specified MQTT topic.",
)
async def subscribe_topic(request: SubscribeTopicRequest) -> MQTTResponse:
    """Subscribe to an MQTT topic."""
    proxies = get_proxies()
    logger = get_logger()

    if "mqtt" not in proxies:
        logger.error("MQTT proxy not available")
        raise HTTPException(
            status_code=503,
            detail="MQTT proxy not available",
            headers={"source": "subscribe_topic"}
        )

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        success = await mqtt_proxy.subscribe_to_topic(topic=request.topic)
        
        if success:
            logger.info(f"Subscribed to topic: {request.topic}")
            return MQTTResponse(status="success", message=f"Subscribed to {request.topic}")
        else:
            logger.error(f"Failed to subscribe to topic: {request.topic}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to subscribe to topic: {request.topic}",
                headers={"source": "subscribe_topic"}
            )

    except Exception as e:
        logger.error(f"Error subscribing to topic: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error subscribing to topic: {str(e)}",
            headers={"source": "subscribe_topic"}
        )

@router.post(
    "/unsubscribe",
    summary="Unsubscribe from MQTT topic",
    description="Unsubscribe from a specified MQTT topic.",
)
async def unsubscribe_topic(request: UnsubscribeTopicRequest) -> MQTTResponse:
    """Unsubscribe from an MQTT topic."""
    proxies = get_proxies()
    logger = get_logger()

    if "mqtt" not in proxies:
        logger.error("MQTT proxy not available")
        raise HTTPException(
            status_code=503,
            detail="MQTT proxy not available",
            headers={"source": "unsubscribe_topic"}
        )

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        success = await mqtt_proxy.unsubscribe_from_topic(topic=request.topic)
        
        if success:
            logger.info(f"Unsubscribed from topic: {request.topic}")
            return MQTTResponse(status="success", message=f"Unsubscribed from {request.topic}")
        else:
            logger.error(f"Failed to unsubscribe from topic: {request.topic}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to unsubscribe from topic: {request.topic}",
                headers={"source": "unsubscribe_topic"}
            )

    except Exception as e:
        logger.error(f"Error unsubscribing from topic: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error unsubscribing from topic: {str(e)}",
            headers={"source": "unsubscribe_topic"}
        )

@router.get(
    "/status",
    summary="Get MQTT proxy status",
    description="Get the current status and health of the MQTT proxy.",
)
async def get_mqtt_status() -> Dict[str, Any]:
    """Get MQTT proxy status and health information."""
    proxies = get_proxies()
    logger = get_logger()

    if "mqtt" not in proxies:
        logger.error("MQTT proxy not available")
        raise HTTPException(
            status_code=503,
            detail="MQTT proxy not available",
            headers={"source": "get_mqtt_status"}
        )

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        health_status = await mqtt_proxy.health_check()
        logger.debug("Retrieved MQTT proxy health status")
        return health_status

    except Exception as e:
        logger.error(f"Error getting MQTT status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting MQTT status: {str(e)}",
            headers={"source": "get_mqtt_status"}
        )

@router.get(
    "/subscriptions",
    summary="List current MQTT subscriptions",
    description="Get list of currently active MQTT topic subscriptions.",
)
async def list_subscriptions() -> Dict[str, Any]:
    """List current MQTT subscriptions."""
    proxies = get_proxies()
    logger = get_logger()

    if "mqtt" not in proxies:
        logger.error("MQTT proxy not available")
        raise HTTPException(
            status_code=503,
            detail="MQTT proxy not available",
            headers={"source": "list_subscriptions"}
        )

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        subscriptions = {
            "topics": list(mqtt_proxy._subscriptions.keys()),
            "patterns": list(mqtt_proxy._subscription_patterns.keys()),
            "count": len(mqtt_proxy._subscriptions) + len(mqtt_proxy._subscription_patterns)
        }
        
        logger.debug(f"Retrieved {subscriptions['count']} MQTT subscriptions")
        return subscriptions

    except Exception as e:
        logger.error(f"Error listing subscriptions: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing subscriptions: {str(e)}",
            headers={"source": "list_subscriptions"}
        )
