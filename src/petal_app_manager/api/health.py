from fastapi import APIRouter, Depends
from typing import Dict, Any, Optional
import time
import logging

# Health endpoints now use the unified health service
from ..api import get_proxies
from ..models.health import (
    BasicHealthResponse,
    OrganizationHealthResponse,
    DetailedHealthResponse,
    OrganizationManagerHealth,
    HealthMessage
)
from ..health_service import get_health_service

router = APIRouter(tags=["health"])

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

@router.get("/health", response_model=BasicHealthResponse)
async def health_check() -> BasicHealthResponse:
    """Basic health check endpoint."""
    logger = get_logger()
    logger.info("Health check requested")
    return BasicHealthResponse(status="ok")

@router.get("/health/organization", response_model=OrganizationHealthResponse)
async def organization_health_check() -> OrganizationHealthResponse:
    """Get current organization information and status."""
    logger = get_logger()
    logger.info("Organization health check requested")
    
    try:
        health_service = get_health_service(logger)
        org_status = await health_service._check_organization_manager_safe()
        return OrganizationHealthResponse(
            status="ok",
            timestamp=time.time(),
            organization_manager=org_status
        )
    except Exception as e:
        logger.error(f"Error in organization health check: {e}")
        # Create error organization status
        error_org_status = OrganizationManagerHealth(
            status="error",
            error=str(e)
        )
        return OrganizationHealthResponse(
            status="error",
            timestamp=time.time(),
            error=str(e),
            organization_manager=error_org_status
        )

@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check() -> DetailedHealthResponse:
    """Comprehensive health check endpoint that reports the status of each proxy."""
    proxies = get_proxies()
    logger = get_logger()
    
    if not proxies:
        logger.warning("Health check requested but no proxies are configured.")
        from ..models.health import HealthStatus, OrganizationManagerHealth
        
        # Create minimal response for no proxies
        error_org_status = OrganizationManagerHealth(
            status=HealthStatus.ERROR,
            error="No proxies configured",
            details="No proxies are configured in the application"
        )
        
        return DetailedHealthResponse(
            status=HealthStatus.ERROR,
            timestamp=time.time(),
            organization_manager=error_org_status,
            proxies={},
            message="No proxies configured"
        )
    
    # Use the unified health service
    health_service = get_health_service(logger)
    return await health_service.get_detailed_health_status(proxies)

@router.get("/health/overview", response_model=HealthMessage)
async def detailed_health_check() -> HealthMessage:
    """Comprehensive health check endpoint that reports the status of each proxy."""
    proxies = get_proxies()
    logger = get_logger()
    
    # Use the unified health service to get HealthMessage format
    health_service = get_health_service(logger)
    return await health_service.get_health_message(proxies)