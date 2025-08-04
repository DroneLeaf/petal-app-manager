# S3 Bucket Proxy Documentation

This document describes the S3BucketProxy implementation for handling flight log storage in AWS S3.

## Overview

The S3BucketProxy provides a secure interface for uploading, downloading, listing, and deleting flight log files (.ulg and .bag extensions) from an AWS S3 bucket. It includes:

- **File validation** for flight log formats
- **AWS session credential management** via session token service
- **Machine-based access control** using robot_instance_id
- **RESTful API endpoints** for file operations

## Features

### File Type Support
- **ULog files** (.ulg): PX4 flight log format
- **ROS Bag files** (.bag): ROS message recording format

### Security Features
- **Session-based authentication** using temporary AWS credentials
- **Machine isolation** - each machine can only access its own files
- **File validation** to ensure only valid flight logs are stored
- **Automatic key generation** with timestamps and machine organization

### API Endpoints

#### Upload File
```
POST /bucket/upload
```
- Upload a flight log file to S3
- Validates file type and content
- Organizes files by machine ID and timestamp

#### List Files
```
GET /bucket/list?prefix=optional_prefix
```
- List files for the current machine
- Optional prefix filtering

#### Download File
```
GET /bucket/download/{s3_key:path}
```
- Download a specific file by S3 key
- Validates machine ownership

#### Delete File
```
DELETE /bucket/delete/{s3_key:path}
```
- Delete a specific file by S3 key
- Validates machine ownership

#### Bucket Info
```
GET /bucket/info
```
- Get bucket configuration and machine information

## Configuration

The S3BucketProxy requires these configuration parameters:

```python
proxy = S3BucketProxy(
    session_token_url="http://localhost:3000/session-token",  # Session service URL
    bucket_name="flight-logs-bucket",                         # S3 bucket name
    region="us-east-1",                                       # AWS region
    upload_prefix="flight_logs/",                             # S3 key prefix
    debug=False,                                             # Debug logging
    request_timeout=30                                       # Request timeout seconds
)
```

## File Organization

Files are organized in S3 using this structure:
```
{upload_prefix}/{machine_id}/{timestamp}_{filename}
```

Example:
```
flight_logs/drone-001/20250727_143022_mission_log.ulg
flight_logs/drone-001/20250727_143045_sensor_data.bag
```

## Session Token Service

The proxy expects a session token service that provides temporary AWS credentials:

```python
def get_session_credentials():
    """Fetch AWS session credentials from the session manager"""
    response = requests.post(session_token_url)
    return response.json()  # Should contain: accessKeyId, secretAccessKey, sessionToken
```

## File Validation

### Extension Validation
Only files with `.ulg` and `.bag` extensions are allowed (case-insensitive).

### Content Validation
- **ULog files**: Must start with "ULogData" magic bytes
- **ROS Bag files**: Must start with "#ROSBAG" header
- **Size limits**: Files must be > 0 bytes and < 2GB

## Usage Examples

### Initialize and Start Proxy
```python
proxy = S3BucketProxy(
    session_token_url="http://session-service:3000/token",
    bucket_name="my-flight-logs",
    region="us-west-2"
)
await proxy.start()
```

### Upload a File
```python
from pathlib import Path

result = await proxy.upload_file(
    file_path=Path("/path/to/flight.ulg"),
    machine_id="drone-123",
    custom_filename="mission_2025_01_15.ulg"
)

if result.get("success"):
    print(f"Uploaded to: {result['s3_key']}")
    print(f"File URL: {result['file_url']}")
```

### List Files
```python
result = await proxy.list_files(machine_id="drone-123")
if result.get("success"):
    for file_info in result.get("files", []):
        print(f"File: {file_info['key']}, Size: {file_info['size']}")
```

### Download a File
```python
result = await proxy.download_file(
    s3_key="flight_logs/drone-123/20250727_143022_mission_log.ulg",
    local_path=Path("/downloads/mission_log.ulg")
)

if result.get("success"):
    print(f"Downloaded to: {result['local_path']}")
```

## Error Handling

The proxy returns structured error responses:

```python
{
    "error": "Description of the error",
    "status": 400  # HTTP status code where applicable
}
```

Common errors:
- **Invalid file extension**: File type not allowed
- **File validation failed**: Content doesn't match expected format
- **Authentication failed**: Session credentials invalid or expired
- **Access denied**: Attempting to access files from another machine
- **File not found**: Requested S3 key doesn't exist

## Integration with Application

To integrate with the main application:

1. **Configure proxy in main application**:
```python
from petal_app_manager.proxies import S3BucketProxy

bucket_proxy = S3BucketProxy(
    session_token_url=config.SESSION_TOKEN_URL,
    bucket_name=config.S3_BUCKET_NAME,
    region=config.AWS_REGION
)

# Add to proxy registry
proxies["bucket"] = bucket_proxy
```

2. **Include API router**:
```python
from petal_app_manager.api import bucket_api

app.include_router(bucket_api.router, prefix="/bucket")
```

3. **Set logger for API endpoints**:
```python
from petal_app_manager.api import bucket_api

bucket_api._set_logger(logger)
```

## AWS Permissions

The session token service should provide credentials with these S3 permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name/*",
                "arn:aws:s3:::your-bucket-name"
            ]
        }
    ]
}
```

## Testing

Use the provided test script to validate the implementation:

```bash
python3 test_bucket_proxy.py
```

This tests file validation, content checking, and S3 key generation without requiring live AWS credentials.
