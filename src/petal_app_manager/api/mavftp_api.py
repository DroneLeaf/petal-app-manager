from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
import time
from pydantic import BaseModel
import logging

# Import proxy types for type hints
from ..proxies.redis import RedisProxy
from ..proxies.localdb import LocalDBProxy
from ..proxies.external import MavLinkExternalProxy
from ..proxies.external import MavLinkFTPProxy
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
    remote_path: str = "/fs/microsd"

@router.post(
    "/clear-error-logs",
    summary="Clears all fail_*.log files from the vehicle.",
    description="This endpoint clears all fail_*.log files from the vehicle's filesystem.",
)
async def clear_fail_logs(
    request: ClearFailLogsRequest
) -> Dict[str, Any]:
    """Clear all fail_*.log files from the vehicle's filesystem."""
    proxies = get_proxies()
    logger = get_logger()
    
    try:
        # Get the MAVLink FTP proxy
        if "ftp_mavlink" not in proxies:
            logger.error("MAVLink FTP proxy not available")
            return {
                "success": False,
                "error": "MAVLink FTP proxy not configured or not available",
                "message": "Cannot clear error logs without MAVLink FTP connection"
            }
        
        mavftp_proxy: MavLinkFTPProxy = proxies["ftp_mavlink"]
        
        # Clear error logs using the proxy
        logger.info(f"Clearing error logs from remote path: {request.remote_path}")
        await mavftp_proxy.clear_error_logs(request.remote_path)
        
        logger.info("Error logs cleared successfully")
        return {
            "success": True,
            "message": "Error logs cleared successfully",
            "remote_path": request.remote_path
        }
        
    except Exception as e:
        logger.error(f"Error clearing fail logs: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to clear error logs from vehicle"
        }
    
@router.post(
    "/list-directory",
    summary="Lists the contents of a directory on the vehicle.",
    description="This endpoint lists the contents of a directory on the vehicle's filesystem.",
)
async def list_directory(
    request: ClearFailLogsRequest
) -> Dict[str, Any]:
    """Clear all fail_*.log files from the vehicle's filesystem."""
    proxies = get_proxies()
    logger = get_logger()
    
    try:
        # Get the MAVLink FTP proxy
        if "ftp_mavlink" not in proxies:
            logger.error("MAVLink FTP proxy not available")
            return {
                "success": False,
                "error": "MAVLink FTP proxy not configured or not available",
                "message": "Cannot clear error logs without MAVLink FTP connection"
            }
        
        mavftp_proxy: MavLinkFTPProxy = proxies["ftp_mavlink"]
        
        # List directory contents using the proxy
        logger.info(f"Listing directory contents at: {request.remote_path}")
        directory_contents = await mavftp_proxy.list_directory(request.remote_path)

        logger.info("Directory contents retrieved successfully")
        return {
            "success": True,
            "message": "Directory contents retrieved successfully",
            "directory_contents": directory_contents
        }
        
    except Exception as e:
        logger.error(f"Error listing directory contents: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to list directory contents from vehicle"
        }