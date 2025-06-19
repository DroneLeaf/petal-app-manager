from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter(tags=["debug"])

@router.get("/proxies")
async def list_proxies():
    """List all available proxies in the system."""
    return {
        "proxies": [
            "ext_mavlink",
            "redis",
            "db"
        ]
    }