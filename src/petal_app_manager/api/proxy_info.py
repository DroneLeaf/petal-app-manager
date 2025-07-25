from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
from ..api import get_proxies
from ..proxies import LocalDBProxy, CloudDBProxy, MavLinkExternalProxy, MavLinkFTPProxy, RedisProxy
import logging

router = APIRouter(tags=["debug"])

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

@router.get("/proxies")
async def list_proxies():
    """List all available proxies in the system."""

    proxies = get_proxies()
    logger = get_logger()

    if not proxies:
        logger.error("No proxies found")
        return {"error": "No proxies available"}
    
    logger.info(f"Available proxies: {', '.join(proxies.keys())}")
    # Return a list of proxy names
    return {
        "proxies": list(proxies.keys())
    }