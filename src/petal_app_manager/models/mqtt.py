"""
Pydantic models for MQTT messages.
"""
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Any, Optional, Union, ClassVar
from datetime import datetime
import time


class MQTTMessage(BaseModel):
    """MQTT message model"""
    waitResponse: bool = Field(..., description="Whether to wait for a response")
    messageId: str = Field(..., description="Unique message ID")
    deviceId: str = Field(..., description="Device ID")
    command: str = Field(..., description="Command to execute")
    timestamp: str = Field(..., description="Timestamp of the message")
    payload: Dict[str, Any] = Field(..., description="Message payload")

    model_config = {
        "json_schema_extra": {
            "example": {
                "waitResponse": True,
                "messageId": "kkkss8fepn-1756665973142-bptyoj06z",
                "deviceId": "Instance-a92c5505-ccdb-4ac7-b0fe-74f4fa5fc5b9",
                "command": "Update",
                "payload": {
                    "source": "web-client",
                    "app": "leaf-fc"
                },
                "timestamp": "2025-08-31T18:46:13.142Z"
            }
        }
    }