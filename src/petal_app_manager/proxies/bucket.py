import asyncio
import concurrent.futures
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
from datetime import datetime

import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError

from .base import BaseProxy
from .localdb import LocalDBProxy

_ULOG_MAGIC   = b"ULog\x01\x12\x35"     # 7‑byte magic    :contentReference[oaicite:0]{index=0}
_ULOG_VERSION = 1                       # current spec
_ROSBAG_MAGIC = b"#ROSBAG"              # first 7 bytes   :contentReference[oaicite:1]{index=1}
_SIZE_LIMIT   = 2 * 1024**3             # 2 GiB

class S3BucketProxy(BaseProxy):
    """
    Proxy for communicating with an S3 bucket for flight log storage.
    Supports upload, download, and listing of .ulg and .bag files.
    """
    
    # Allowed file extensions for flight logs
    ALLOWED_EXTENSIONS = {'.ulg', '.bag'}
    
    def __init__(
        self,
        session_token_url: str,
        bucket_name: str,
        local_db_proxy: LocalDBProxy,
        upload_prefix: str = 'flight_logs/',
        debug: bool = False,
        request_timeout: int = 30
    ):
        self.session_token_url = session_token_url
        self.bucket_name = bucket_name
        self.local_db_proxy = local_db_proxy
        self.upload_prefix = upload_prefix.rstrip('/') + '/'
        self.debug = debug
        self.request_timeout = request_timeout
        
        self._loop = None
        self._exe = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.log = logging.getLogger("S3BucketProxy")
        
        # Session management
        self._session_cache = {
            'credentials': None,
            'expires_at': 0
        }
        
        # S3 client (will be initialized in start())
        self.s3_client = None

    async def start(self):
        """Initialize the S3 proxy and fetch initial credentials."""
        self._loop = asyncio.get_running_loop()
        self.log.info("Initializing S3BucketProxy connection")
        
        # Validate configuration
        if not self.session_token_url or not self.bucket_name:
            raise ValueError("SESSION_TOKEN_URL and BUCKET_NAME must be configured")
        
        # Fetch initial credentials and create S3 client
        try:
            credentials = await self._get_session_credentials()
            self.s3_client = self._create_s3_client(credentials)
            self.log.info("S3BucketProxy started successfully")
        except Exception as e:
            self.log.error(f"Failed to initialize S3BucketProxy: {e}")
            # raise
        
    async def stop(self):
        """Clean up resources when shutting down."""
        self._exe.shutdown(wait=False)
        self.s3_client = None
        self.log.info("S3BucketProxy stopped")

    def _get_machine_id(self) -> Optional[str]:
        """
        Get the machine ID from the LocalDBProxy.
        
        Returns:
            The machine ID if available, None otherwise
        """
        if not self.local_db_proxy:
            self.log.error("LocalDBProxy not available")
            return None
        
        machine_id = self.local_db_proxy.machine_id
        if not machine_id:
            self.log.error("Machine ID not available from LocalDBProxy")
            return None
        
        return machine_id
        
    def _validate_file_extension(self, filename: str) -> bool:
        """
        Validate that the file has an allowed extension for flight logs.
        
        Args:
            filename: The filename to validate
            
        Returns:
            True if the file extension is allowed, False otherwise
        """
        if not filename:
            return False
            
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        
        return extension in self.ALLOWED_EXTENSIONS
    
    def _validate_file_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Basic validation of PX4 ULog (*.ulg) and ROS1 bag (*.bag) flight‑log files.
        Returns a dict with either {"valid": True, ...} or {"valid": False, "error": ...}.
        """
        try:
            # ---------- existence & size -------------------------------------------------
            if not file_path.exists():
                return {"valid": False, "error": "File does not exist"}

            size = file_path.stat().st_size
            if size == 0:
                return {"valid": False, "error": "File is empty"}
            if size > _SIZE_LIMIT:
                return {"valid": False, "error": "File too large (max 2 GiB)"}

            # ---------- content sniff ----------------------------------------------------
            ext = file_path.suffix.lower()

            if ext == ".ulg":
                with file_path.open("rb") as f:
                    header = f.read(8)  # 7‑byte magic + 1‑byte version
                if not (header[:7] == _ULOG_MAGIC and header[7] == _ULOG_VERSION):
                    return {"valid": False,
                            "error": "Invalid ULog header (magic/version mismatch)"}

            elif ext == ".bag":
                with file_path.open("rb") as f:
                    header = f.read(8)  # '#ROSBAG'
                if not header.startswith(_ROSBAG_MAGIC):
                    return {"valid": False,
                            "error": "Invalid ROS bag header (expected '#ROSBAG')"}

            else:
                return {"valid": False,
                        "error": f"Unsupported extension '{ext}'"}

            # ---------- success ----------------------------------------------------------
            return {"valid": True,
                    "file_size": size,
                    "extension": ext}

        except Exception as e:
            # log & bubble up a clean error object
            self.log.error("File validation error: %s", e)
            return {"valid": False, "error": f"Validation failed: {e}"}
        
    async def _get_session_credentials(self) -> Dict[str, Any]:
        """
        Fetch AWS session credentials from the session manager with caching.
        
        Returns:
            Dictionary containing AWS session credentials
        """
        current_time = time.time()

        # Check if we have cached credentials that haven't expired
        if (self._session_cache['credentials'] and
            current_time < self._session_cache['expires_at']):
            return self._session_cache['credentials']

        def _fetch_credentials():
            try:
                self.log.info("Fetching new session credentials")
                response = requests.post(
                    self.session_token_url,
                    timeout=self.request_timeout
                )
                response.raise_for_status()

                credentials = response.json()

                # Validate required fields
                required_fields = ['accessKeyId', 'secretAccessKey', 'sessionToken']
                for field in required_fields:
                    if field not in credentials:
                        raise ValueError(f"Missing required field: {field}")

                # Cache credentials for 50 minutes (assume 1-hour expiry)
                self._session_cache['credentials'] = credentials
                self._session_cache['expires_at'] = current_time + (50 * 60)

                self.log.info("Session credentials updated successfully")
                return credentials

            except requests.exceptions.Timeout:
                self.log.error("Session token request timed out")
                raise Exception("Session service timeout")
            except requests.exceptions.RequestException as e:
                self.log.error(f"Session token request failed: {str(e)}")
                raise Exception(f"Failed to fetch session credentials: {str(e)}")
            except ValueError as e:
                self.log.error(f"Invalid credentials response: {str(e)}")
                raise Exception(f"Invalid credentials response: {str(e)}")
            except Exception as e:
                self.log.error(f"Unexpected error getting session credentials: {str(e)}")
                raise Exception(f"Authentication service error: {str(e)}")

        try:
            return await self._loop.run_in_executor(self._exe, _fetch_credentials)
        except Exception as e:
            self.log.error(f"Failed to execute credential fetch: {str(e)}")
            # Re-raise with a more user-friendly message or handle as needed
            raise Exception(f"Credential fetch operation failed: {str(e)}")
    
    def _create_s3_client(self, credentials: Dict[str, Any]) -> boto3.client:
        """Create S3 client with session credentials"""
        try:
            return boto3.client(
                's3',
                aws_access_key_id=credentials['accessKeyId'],
                aws_secret_access_key=credentials['secretAccessKey'],
                aws_session_token=credentials['sessionToken']
            )
        except Exception as e:
            self.log.error(f"Failed to create S3 client: {str(e)}")
            raise Exception("Failed to initialize storage client")
    
    def _generate_s3_key(self, filename: str, machine_id: str) -> str:
        """
        Generate a unique S3 key for the file.
        
        Args:
            filename: Original filename
            machine_id: Machine ID for organization
            
        Returns:
            S3 key string
        """
        # Create timestamp for organization
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        
        # Clean filename and add UUID for uniqueness
        clean_filename = Path(filename).name
        unique_filename = f"{uuid.uuid4()}_{clean_filename}"
        
        # Generate key: machine_id/flight-logs/YYYYMMDD_HHMMSS_uuid_filename
        return f"{machine_id}/flight-logs/{timestamp}_{unique_filename}"
        
    async def _refresh_s3_client(self):
        """Refresh the S3 client with new credentials if needed."""
        try:
            credentials = await self._get_session_credentials()
            self.s3_client = self._create_s3_client(credentials)
        except Exception as e:
            self.log.error(f"Failed to refresh S3 client: {e}")
            # raise
    
    # ------ Public API methods ------ #
    
    async def upload_file(self, file_path: Path, 
                         custom_filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a flight log file to S3.
        
        Args:
            file_path: Path to the local file to upload
            custom_filename: Optional custom filename (defaults to original)
            
        Returns:
            Dictionary with upload results
        """
        # Get machine ID from LocalDBProxy
        machine_id = self._get_machine_id()
        if not machine_id:
            return {"error": "Machine ID not available"}
        
        def _upload():
            try:
                filename = custom_filename or file_path.name
                
                # Validate file extension
                if not self._validate_file_extension(filename):
                    return {
                        "error": f"Invalid file extension. Only {', '.join(self.ALLOWED_EXTENSIONS)} files are allowed",
                        "allowed_extensions": list(self.ALLOWED_EXTENSIONS)
                    }
                
                # Validate file content
                validation_result = self._validate_file_content(file_path)
                if not validation_result["valid"]:
                    return {"error": f"File validation failed: {validation_result['error']}"}
                
                # Generate S3 key
                s3_key = self._generate_s3_key(filename, machine_id)
                
                # Determine content type
                extension = Path(filename).suffix.lower()
                content_type = 'application/octet-stream'
                if extension == '.ulg':
                    content_type = 'application/x-ulog'
                elif extension == '.bag':
                    content_type = 'application/x-rosbag'
                
                # Upload to S3 using boto3
                self.s3_client.upload_file(
                    str(file_path),
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': content_type,
                        'ServerSideEncryption': 'AES256',
                        'Metadata': {
                            'original-filename': filename,
                            'upload-timestamp': str(int(time.time())),
                            'machine-id': machine_id
                        }
                    }
                )
                
                file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                self.log.info(f"Successfully uploaded {filename} to {s3_key}")
                
                return {
                    "success": True,
                    "s3_key": s3_key,
                    "file_url": file_url,
                    "file_size": validation_result["file_size"],
                    "content_type": content_type
                }
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                self.log.error(f"S3 upload failed: {error_code}")
                return {"error": f"Upload failed: {error_code}"}
            except Exception as e:
                self.log.error(f"Upload error: {e}")
                return {"error": f"Upload failed: {str(e)}"}
        
        # Ensure we have a valid S3 client
        try:
            await self._refresh_s3_client()
            return await self._loop.run_in_executor(self._exe, _upload)
        except Exception as e:
            return {"error": f"Client initialization failed: {str(e)}"}
    
    async def list_files(self, prefix: Optional[str] = None, max_keys: int = 100) -> Dict[str, Any]:
        """
        List files in the S3 bucket for the current machine.
        
        Args:
            prefix: Optional additional prefix to filter by
            max_keys: Maximum number of files to return (default 100, max 1000)
            
        Returns:
            Dictionary with list of files
        """
        # Get machine ID from LocalDBProxy
        machine_id = self._get_machine_id()
        if not machine_id:
            return {"error": "Machine ID not available"}
        
        def _list():
            try:
                # Build the prefix for listing with new structure: machine_id/flight-logs/
                list_prefix = f"{machine_id}/flight-logs/"
                
                if prefix:
                    list_prefix += prefix
                
                # Limit max_keys to prevent excessive results
                limited_max_keys = min(max_keys, 1000)
                
                # List objects using boto3
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=list_prefix,
                    MaxKeys=limited_max_keys
                )
                
                files = []
                if 'Contents' in response:
                    for obj in response['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'].isoformat(),
                            'url': f"https://{self.bucket_name}.s3.amazonaws.com/{obj['Key']}"
                        })
                
                self.log.info(f"Listed {len(files)} files with prefix: {list_prefix}")
                
                return {
                    "success": True,
                    "files": files,
                    "total_count": len(files),
                    "is_truncated": response.get('IsTruncated', False),
                    "prefix": list_prefix
                }
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                self.log.error(f"S3 list failed: {error_code}")
                return {"error": f"List failed: {error_code}"}
            except Exception as e:
                self.log.error(f"List error: {e}")
                return {"error": f"List failed: {str(e)}"}
        
        # Ensure we have a valid S3 client
        try:
            await self._refresh_s3_client()
            return await self._loop.run_in_executor(self._exe, _list)
        except Exception as e:
            return {"error": f"Client initialization failed: {str(e)}"}
    
    async def download_file(self, s3_key: str, local_path: Path) -> Dict[str, Any]:
        """
        Download a file from S3.
        
        Args:
            s3_key: S3 key of the file to download
            local_path: Local path where to save the file
            
        Returns:
            Dictionary with download results
        """
        def _download():
            try:
                # Validate that the key is for an allowed file type
                if not self._validate_file_extension(s3_key):
                    return {"error": "File type not allowed for download"}
                
                # Create parent directories if they don't exist
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download from S3 using boto3
                self.s3_client.download_file(
                    self.bucket_name,
                    s3_key,
                    str(local_path)
                )
                
                # Get file size after download
                file_size = local_path.stat().st_size
                self.log.info(f"Successfully downloaded {s3_key} to {local_path}")
                
                return {
                    "success": True,
                    "local_path": str(local_path),
                    "file_size": file_size,
                    "s3_key": s3_key
                }
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchKey':
                    self.log.warning(f"File not found: {s3_key}")
                    return {"error": "File not found"}
                else:
                    self.log.error(f"S3 download failed: {error_code}")
                    return {"error": f"Download failed: {error_code}"}
            except Exception as e:
                self.log.error(f"Download error: {e}")
                return {"error": f"Download failed: {str(e)}"}
        
        # Ensure we have a valid S3 client
        try:
            await self._refresh_s3_client()
            return await self._loop.run_in_executor(self._exe, _download)
        except Exception as e:
            return {"error": f"Client initialization failed: {str(e)}"}
    
    async def delete_file(self, s3_key: str) -> Dict[str, Any]:
        """
        Delete a file from S3.
        
        Args:
            s3_key: S3 key of the file to delete
            
        Returns:
            Dictionary with deletion results
        """
        def _delete():
            try:
                # Delete file from S3 using boto3
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
                
                self.log.info(f"Successfully deleted {s3_key}")
                return {
                    "success": True,
                    "s3_key": s3_key,
                    "message": "File deleted successfully"
                }
                
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'NoSuchKey':
                    self.log.warning(f"File not found: {s3_key}")
                    return {"error": "File not found"}
                else:
                    self.log.error(f"S3 delete failed: {error_code}")
                    return {"error": f"Delete failed: {error_code}"}
            except Exception as e:
                self.log.error(f"Delete error: {e}")
                return {"error": f"Delete failed: {str(e)}"}
        
        # Ensure we have a valid S3 client
        try:
            await self._refresh_s3_client()
            return await self._loop.run_in_executor(self._exe, _delete)
        except Exception as e:
            return {"error": f"Client initialization failed: {str(e)}"}
