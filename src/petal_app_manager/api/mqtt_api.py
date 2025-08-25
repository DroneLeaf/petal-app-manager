from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import logging
import os

# Import proxy types for type hints
from ..proxies.mqtt import MQTTProxy
from ..api import get_proxies

router = APIRouter(tags=["mqtt"], prefix="/mqtt")

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the logger for api endpoints."""
    global _logger
    _logger = logger

def get_logger() -> logging.Logger:
    """Get the logger instance."""
    global _logger
    if not _logger:
        _logger = logging.getLogger("BucketAPI")
    return _logger

@router.post(
    "/callback",
    summary="callback server handling in MQTT proxy",
    description="Handle incoming callback messages from the MQTT broker.",
)
async def handle_callback(
    message_data: Dict[Any, Any]
) -> Dict[str, Any]:
    """Handle incoming callback messages from the MQTT broker."""
    proxies = get_proxies()
    logger = get_logger()

    mqtt_proxy: MQTTProxy = proxies["mqtt"]

    try:
        mqtt_proxy._process_received_message(message_data)
        return {'status': 'success'}

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during upload: {str(e)}")
