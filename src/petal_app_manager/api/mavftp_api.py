from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
import time
from pydantic import BaseModel
import logging

# Import proxy types for type hints
from ..proxies.redis import RedisProxy
from ..proxies.localdb import LocalDBProxy
from ..proxies.external import MavLinkExternalProxy
from ..proxies.cloud import CloudDBProxy
from ..proxies.bucket import S3BucketProxy
from ..api import get_proxies

router = APIRouter(tags=["mavftp"])

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

class ClearFailLogsRequest(BaseModel):
    remote_path: str = "fs/microsd"

@router.post(
    "/clear-error-logs",
    summary="Clears all fail_*.log files from the vehicle.",
    description="This endpoint clears all fail_*.log files from the vehicle's filesystem.",
)
async def clear_fail_logs(
    request: ClearFailLogsRequest
) -> Dict[str, Any]:
    """List all data in a particular table in the cloud database."""
    proxies = get_proxies()
    logger = get_logger()