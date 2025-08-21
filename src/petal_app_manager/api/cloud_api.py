
from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
from fastapi.exceptions import HTTPException
from pydantic import BaseModel
import logging

# Import proxy types for type hints
from ..proxies.localdb import LocalDBProxy
from ..proxies.cloud import CloudDBProxy
from ..api import get_proxies

router = APIRouter(tags=["cloud"])

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
class ScanTableRequest(BaseModel):
    table_name: str
    filters: list = []

class GetItemRequest(BaseModel):
    table_name: str
    key_name: str
    key_value: str

class SetItemRequest(BaseModel):
    table_name: str
    item_data: Dict[str, Any]

class UpdateItemRequest(BaseModel):
    table_name: str
    key_name: str
    key_value: str
    update_data: Dict[str, Any]

@router.post(
    "/scan-table",
    summary="Get all records from cloud for a specific table",
    description="Retrieves all records for the current organization from the cloud database.",
)
async def scan_table(request: ScanTableRequest) -> Dict[str, Any]:
    """List all data in a particular table in the cloud database."""
    proxies = get_proxies()
    logger = get_logger()

    if "cloud" not in proxies:
        logger.error("CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml.")
        raise HTTPException(
            status_code=503,
            detail="CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml."
        )

    cloud_proxy: CloudDBProxy = proxies["cloud"]

    # get table name from request data
    table_name = request.table_name

    if not table_name:
        logger.error("Table name is required to scan items in cloud")
        raise HTTPException(
            status_code=400,
            detail="Table name is required",
            headers={"source": "scan_table"}
        )

    try:
        # Use the filters from request - robot_instance_id filtering is handled automatically by the proxy
        result = await cloud_proxy.scan_items(
            table_name=table_name, 
            filters=request.filters
        )

        if "error" in result:
            logger.error(f"Failed to retrieve records from cloud: {result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve records from cloud: {result['error']}",
                headers={"source": "scan_table"}
            )
        
        records = result.get("data", [])

        logger.info(
            f"Retrieved {len(records)} records from cloud table {table_name} "
            f"for machine {cloud_proxy._get_machine_id()}"
        )

        # Process and return the records
        return {"records": records, "count": len(records)}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving cloud records: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error retrieving cloud records: {str(e)}",
            headers={"source": "scan_table"}
        )

@router.post(
    "/get-item",
    summary="Get a specific item from cloud database",
    description="Retrieves a specific item by key from the cloud database.",
)
async def get_item(request: GetItemRequest) -> Dict[str, Any]:
    """Get a specific item from the cloud database."""
    proxies = get_proxies()
    logger = get_logger()

    if "cloud" not in proxies:
        logger.error("CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml.")
        raise HTTPException(
            status_code=503,
            detail="CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml."
        )

    cloud_proxy: CloudDBProxy = proxies["cloud"]

    if not request.table_name or not request.key_name or not request.key_value:
        logger.error("Table name, key name, and key value are required")
        raise HTTPException(
            status_code=400,
            detail="Table name, key name, and key value are required",
            headers={"source": "get_item"}
        )

    try:
        result = await cloud_proxy.get_item(
            table_name=request.table_name,
            partition_key=request.key_name,
            partition_value=request.key_value
        )

        if "error" in result:
            logger.error(f"Failed to retrieve item from cloud: {result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve item from cloud: {result['error']}",
                headers={"source": "get_item"}
            )

        item = result.get("data")
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Item not found in cloud database",
                headers={"source": "get_item"}
            )

        logger.info(
            f"Retrieved item {request.key_value} from cloud table {request.table_name}"
        )

        return {"item": item}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving cloud item: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error retrieving cloud item: {str(e)}",
            headers={"source": "get_item"}
        )

@router.post(
    "/set-item",
    summary="Create or overwrite an item in cloud database",
    description="Creates a new item or overwrites an existing item in the cloud database.",
)
async def set_item(request: SetItemRequest) -> Dict[str, Any]:
    """Create or overwrite an item in the cloud database."""
    proxies = get_proxies()
    logger = get_logger()

    if "cloud" not in proxies:
        logger.error("CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml.")
        raise HTTPException(
            status_code=503,
            detail="CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml."
        )

    cloud_proxy: CloudDBProxy = proxies["cloud"]

    if not request.table_name or not request.item_data:
        logger.error("Table name and item data are required")
        raise HTTPException(
            status_code=400,
            detail="Table name and item data are required",
            headers={"source": "set_item"}
        )

    try:
        # Add robot_instance_id to the item data if not present - this is handled automatically by the proxy
        item_data = request.item_data.copy()

        result = await cloud_proxy.set_item(
            table_name=request.table_name,
            filter_key="id",  # Use id as the primary key instead of organization_id
            filter_value=item_data.get("id", ""),  # Get id from item_data
            data=item_data
        )

        if "error" in result:
            logger.error(f"Failed to set item in cloud: {result['error']}")
            raise HTTPException(
                status_code=500,
                detail="Failed to set item in cloud",
                headers={"source": "set_item"},
                extra={"error": result["error"]}
            )

        logger.info(f"Successfully set item in cloud table {request.table_name}")

        return {"success": True, "message": "Item created/updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error setting cloud item: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error setting cloud item: {str(e)}",
            headers={"source": "set_item"}
        )

@router.post(
    "/update-item",
    summary="Update an existing item in cloud database",
    description="Updates specific fields of an existing item in the cloud database.",
)
async def update_item(request: UpdateItemRequest) -> Dict[str, Any]:
    """Update an existing item in the cloud database."""
    proxies = get_proxies()
    logger = get_logger()

    if "cloud" not in proxies:
        logger.error("CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml.")
        raise HTTPException(
            status_code=503,
            detail="CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml."
        )

    cloud_proxy: CloudDBProxy = proxies["cloud"]

    if not request.table_name or not request.key_name or not request.key_value or not request.update_data:
        logger.error("Table name, key name, key value, and update data are required")
        raise HTTPException(
            status_code=400,
            detail="Table name, key name, key value, and update data are required",
            headers={"source": "update_item"}
        )

    try:
        result = await cloud_proxy.update_item(
            table_name=request.table_name,
            filter_key=request.key_name,
            filter_value=request.key_value,
            data=request.update_data
        )
 
        if "error" in result:
            logger.error(f"Failed to update item in cloud: {result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update item in cloud {result['error']}",
                headers={"source": "update_item"}
            )

        logger.info(
            f"Successfully updated item {request.key_value} in cloud table {request.table_name}"
        )

        return {"success": True, "message": "Item updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating cloud item: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error updating cloud item: {str(e)}",
            headers={"source": "update_item"}
        )
    
@router.delete(
    "/delete-item",
    summary="Delete an item from cloud database",
    description="Deletes a specific item from the cloud database.",
)
async def delete_item(request: GetItemRequest) -> Dict[str, Any]:
    """Delete an item from the cloud database."""
    proxies = get_proxies()
    logger = get_logger()

    if "cloud" not in proxies:
        logger.error("CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml.")
        raise HTTPException(
            status_code=503,
            detail="CloudDBProxy is not enabled. Please enable 'cloud' in proxies.yaml."
        )

    cloud_proxy: CloudDBProxy = proxies["cloud"]

    if not request.table_name or not request.key_name or not request.key_value:
        logger.error("Table name, key name, and key value are required")
        raise HTTPException(
            status_code=400,
            detail="Table name, key name, and key value are required",
            headers={"source": "delete_item"}
        )

    try:
        result = await cloud_proxy.delete_item(
            table_name=request.table_name,
            filter_key=request.key_name,
            filter_value=request.key_value
        )

        if "error" in result:
            logger.error(f"Failed to delete item from cloud: {result['error']}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete item from cloud: {result['error']}",
                headers={"source": "delete_item"}
            )

        logger.info(
            f"Successfully deleted item {request.key_value} from cloud table {request.table_name}"
        )

        return {"success": True, "message": "Item deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting cloud item: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error deleting cloud item: {str(e)}",
            headers={"source": "delete_item"}
        )