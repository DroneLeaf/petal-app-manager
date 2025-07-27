from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Response
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional
from pathlib import Path
import tempfile
import logging
import os

# Import proxy types for type hints
from ..proxies.localdb import LocalDBProxy
from ..proxies.bucket import S3BucketProxy
from ..api import get_proxies

router = APIRouter(tags=["bucket"], prefix="/bucket")

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
    "/upload",
    summary="Upload a flight log file to S3 bucket",
    description="Upload a .ulg or .bag flight log file to the S3 bucket storage and return the S3 key.",
)
async def upload_file_test(
    file: UploadFile = File(...),
    custom_filename: Optional[str] = Form(None),
    test_machine_id: Optional[str] = Form("test-machine-123")
) -> Dict[str, Any]:
    """Upload a flight log file to S3 bucket storage for testing."""
    proxies = get_proxies()
    logger = get_logger()

    bucket_proxy: S3BucketProxy = proxies["bucket"]

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    try:
        # Use provided machine ID for testing, fallback to localdb if available
        machine_id = test_machine_id
        if not machine_id and "db" in proxies:
            local_db_proxy: LocalDBProxy = proxies["db"]
            machine_result = await local_db_proxy.machine_id
            if not machine_result.get("error"):
                machine_id = machine_result["machine_id"]
        
        if not machine_id:
            machine_id = "test-machine-default"

        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = Path(temp_file.name)

        try:
            # Upload file using bucket proxy
            result = await bucket_proxy.upload_file(
                temp_file_path, 
                machine_id, 
                custom_filename or file.filename
            )

            if result.get("error"):
                raise HTTPException(status_code=400, detail=result["error"])

            logger.info(f"Successfully uploaded file: {result['s3_key']}")
            return {
                "success": True,
                "message": "File uploaded successfully",
                "s3_key": result["s3_key"],
                "file_url": result["file_url"],
                "file_size": result["file_size"],
                "content_type": result["content_type"],
                "machine_id": machine_id,
                "original_filename": file.filename
            }

        finally:
            # Clean up temporary file
            temp_file_path.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during upload: {str(e)}")

@router.get(
    "/list",
    summary="List flight log files in S3 bucket",
    description="List all flight log files stored in the S3 bucket, optionally filtered by machine ID.",
)
async def list_files_test(
    machine_id: Optional[str] = Query(None, description="Machine ID to filter by"),
    prefix: Optional[str] = Query(None, description="Additional prefix to filter by"),
    max_keys: int = Query(100, le=1000, description="Maximum number of files to return")
) -> Dict[str, Any]:
    """List flight log files in S3 bucket for testing."""
    proxies = get_proxies()
    logger = get_logger()

    bucket_proxy: S3BucketProxy = proxies["bucket"]

    try:
        # Use provided machine_id, or get from localdb if available
        if not machine_id and "db" in proxies:
            local_db_proxy: LocalDBProxy = proxies["db"]
            machine_result = await local_db_proxy.machine_id
            if not machine_result.get("error"):
                machine_id = machine_result["machine_id"]

        # List files for the specified machine (or all if no machine_id)
        result = await bucket_proxy.list_files(
            machine_id=machine_id,
            prefix=prefix,
            max_keys=max_keys
        )

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        logger.info(f"Listed {len(result.get('files', []))} files for machine {machine_id or 'all'}")

        return {
            "success": True,
            "message": "Files listed successfully",
            "machine_id": machine_id,
            "files": result["files"],
            "total_count": result["total_count"],
            "is_truncated": result["is_truncated"],
            "prefix": result["prefix"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during list: {str(e)}")

@router.get(
    "/download/{s3_key:path}",
    summary="Download a flight log file from S3 bucket",
    description="Download a specific flight log file from the S3 bucket using its S3 key.",
)
async def download_file_test(
    s3_key: str,
    return_file: bool = Query(False, description="If true, return the file content directly")
) -> Dict[str, Any]:
    """Download a flight log file from S3 bucket for testing."""
    proxies = get_proxies()
    logger = get_logger()

    bucket_proxy: S3BucketProxy = proxies["bucket"]

    if not s3_key:
        raise HTTPException(status_code=400, detail="S3 key is required")

    try:
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as temp_file:
            temp_file_path = Path(temp_file.name)

        try:
            # Download from S3 using the bucket proxy
            result = await bucket_proxy.download_file(s3_key, temp_file_path)

            if result.get("error"):
                status_code = 404 if "not found" in result["error"].lower() else 500
                raise HTTPException(status_code=status_code, detail=result["error"])

            logger.info(f"Successfully downloaded {s3_key}")

            # If return_file is True, return the file as a download
            if return_file:
                # Extract original filename from s3_key for better download experience
                filename = Path(s3_key).name
                return FileResponse(
                    path=str(temp_file_path),
                    filename=filename,
                    media_type='application/octet-stream'
                )

            # Otherwise return file info
            return {
                "success": True,
                "message": "File downloaded successfully",
                "s3_key": result["s3_key"],
                "file_size": result["file_size"],
                "local_path": result["local_path"],
                "note": "File downloaded to temporary location. Use return_file=true to get file content."
            }

        finally:
            # Clean up temporary file if not returning it
            if not return_file:
                temp_file_path.unlink(missing_ok=True)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during download: {str(e)}")

@router.delete(
    "/delete/{s3_key:path}",
    summary="Delete a flight log file from S3 bucket",
    description="Delete a specific flight log file from the S3 bucket using its S3 key.",
)
async def delete_file_test(s3_key: str) -> Dict[str, Any]:
    """Delete a flight log file from S3 bucket for testing."""
    proxies = get_proxies()
    logger = get_logger()

    bucket_proxy: S3BucketProxy = proxies["bucket"]

    if not s3_key:
        raise HTTPException(status_code=400, detail="S3 key is required")

    try:
        # Delete from S3 using the bucket proxy
        result = await bucket_proxy.delete_file(s3_key)

        if result.get("error"):
            status_code = 404 if "not found" in result["error"].lower() else 500
            raise HTTPException(status_code=status_code, detail=result["error"])

        logger.info(f"Successfully deleted {s3_key}")

        return {
            "success": True,
            "message": result["message"],
            "s3_key": result["s3_key"]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error during delete: {str(e)}")

@router.get(
    "/health",
    summary="Health check for S3 bucket proxy",
    description="Check if the S3 bucket proxy is working and can connect to AWS."
)
async def health_check() -> Dict[str, Any]:
    """Health check for S3 bucket proxy."""
    proxies = get_proxies()
    logger = get_logger()

    try:
        bucket_proxy: S3BucketProxy = proxies["bucket"]
        
        # Try to get session credentials to test connectivity
        credentials = await bucket_proxy._get_session_credentials()
        
        return {
            "success": True,
            "status": "healthy",
            "message": "S3 bucket proxy is working",
            "bucket_name": bucket_proxy.bucket_name,
            "upload_prefix": bucket_proxy.upload_prefix,
            "credentials_cached": bool(credentials)
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "status": "unhealthy",
            "message": f"S3 bucket proxy error: {str(e)}"
        }

@router.get(
    "/info",
    summary="Get S3 bucket proxy information",
    description="Get configuration and status information about the S3 bucket proxy."
)
async def get_info() -> Dict[str, Any]:
    """Get S3 bucket proxy information."""
    proxies = get_proxies()
    
    try:
        bucket_proxy: S3BucketProxy = proxies["bucket"]
        
        return {
            "success": True,
            "config": {
                "bucket_name": bucket_proxy.bucket_name,
                "upload_prefix": bucket_proxy.upload_prefix,
                "allowed_extensions": list(bucket_proxy.ALLOWED_EXTENSIONS),
                "request_timeout": bucket_proxy.request_timeout,
                "debug": bucket_proxy.debug,
                "session_token_url": bucket_proxy.session_token_url.split('@')[-1] if '@' in bucket_proxy.session_token_url else bucket_proxy.session_token_url  # Hide credentials in URL
            },
            "status": {
                "s3_client_initialized": bucket_proxy.s3_client is not None,
                "credentials_cached": bucket_proxy._session_cache['credentials'] is not None,
                "credentials_expire_time": bucket_proxy._session_cache['expires_at']
            }
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to get proxy info: {str(e)}"
        }
