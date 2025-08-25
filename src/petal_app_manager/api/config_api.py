from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import yaml
import os
import sys
import signal
from pathlib import Path
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/petal-proxies-control", tags=["petal-proxies-control"])

_logger: Optional[logging.Logger] = None

def _set_logger(logger: logging.Logger):
    """Set the logger for api endpoints."""
    global _logger
    _logger = logger

def get_logger() -> logging.Logger:
    """Get the logger instance."""
    global _logger
    if not _logger:
        _logger = logging.getLogger("ConfigAPI")
    return _logger

class PetalControlRequest(BaseModel):
    petals: List[str]
    action: str  # "ON" or "OFF"

class ConfigResponse(BaseModel):
    enabled_proxies: List[str]
    enabled_petals: List[str]
    petal_dependencies: Dict[str, List[str]]
    proxy_dependencies: Dict[str, List[str]]
    restart_required: bool = False

@router.get("/status", response_model=ConfigResponse)
async def get_config_status():
    """Get current proxy and petal configuration"""
    logger = get_logger()
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
        
        logger.info("Retrieved current configuration status")
        return ConfigResponse(
            enabled_proxies=config.get("enabled_proxies", []) or [],
            enabled_petals=config.get("enabled_petals", []) or [],
            petal_dependencies=config.get("petal_dependencies", {}),
            proxy_dependencies=config.get("proxy_dependencies", {}),
            restart_required=True  # Always true since we need restart for petal changes
        )
    except Exception as e:
        logger.error(f"Error reading configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read configuration: {str(e)}"
        )

@router.post("/petals/control")
async def control_petals(request: PetalControlRequest) -> Dict[str, Any]:
    """Enable or disable one or more petals"""
    logger = get_logger()
    
    # Validate action
    if request.action.upper() not in ["ON", "OFF"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be either 'ON' or 'OFF'"
        )
    
    # Validate petals list
    if not request.petals:
        raise HTTPException(
            status_code=400,
            detail="At least one petal name must be provided"
        )
    
    action = request.action.upper()
    enable_petals = action == "ON"
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        
        # Read current configuration
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
        
        enabled_petals = set(config.get("enabled_petals", []) or [])
        enabled_proxies = set(config.get("enabled_proxies", []) or [])
        petal_dependencies = config.get("petal_dependencies", {})
        
        results = []
        errors = []
        
        for petal_name in request.petals:
            try:
                if enable_petals:
                    # Check if dependencies are met before enabling
                    required_deps = petal_dependencies.get(petal_name, [])
                    missing_deps = [dep for dep in required_deps if dep not in enabled_proxies]
                    
                    if missing_deps:
                        error_msg = (
                            f"Cannot enable {petal_name}: missing dependencies {missing_deps}. "
                            f"Enable those proxies first."
                        )
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    enabled_petals.add(petal_name)
                    results.append(f"Enabled petal: {petal_name}")
                    logger.info(f"Enabled petal: {petal_name}")
                    
                else:
                    # Disable petal
                    enabled_petals.discard(petal_name)
                    results.append(f"Disabled petal: {petal_name}")
                    logger.info(f"Disabled petal: {petal_name}")
                    
            except Exception as e:
                error_msg = f"Error processing {petal_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Update configuration
        config["enabled_petals"] = list(enabled_petals)
        
        # Write back to file
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        
        logger.info(f"Configuration updated with {len(results)} successful changes")
        
        response = {
            "success": len(results) > 0,
            "action": action,
            "processed_petals": request.petals,
            "results": results,
            "restart_required": True,
            "message": f"Configuration updated. {len(results)} petals {action.lower()}ed successfully."
        }
        
        if errors:
            response["errors"] = errors
            response["partial_success"] = len(results) > 0
        
        return response
        
    except Exception as e:
        logger.error(f"Error updating petal configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )

@router.post("/proxies/control")
async def control_proxies(request: PetalControlRequest) -> Dict[str, Any]:
    """Enable or disable one or more proxies"""
    logger = get_logger()
    
    # Validate action
    if request.action.upper() not in ["ON", "OFF"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be either 'ON' or 'OFF'"
        )
    
    # Validate proxies list (reusing petals field name for consistency)
    if not request.petals:
        raise HTTPException(
            status_code=400,
            detail="At least one proxy name must be provided"
        )
    
    action = request.action.upper()
    enable_proxies = action == "ON"
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        
        # Read current configuration
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
        
        enabled_proxies = set(config.get("enabled_proxies", []) or [])
        enabled_petals = set(config.get("enabled_petals", []) or [])
        petal_dependencies = config.get("petal_dependencies", {})
        proxy_dependencies = config.get("proxy_dependencies", {})
        
        results = []
        errors = []
        
        for proxy_name in request.petals:  # Using petals field for proxy names
            try:
                if enable_proxies:
                    # Check if dependencies are met before enabling
                    required_deps = proxy_dependencies.get(proxy_name, [])
                    missing_deps = [dep for dep in required_deps if dep not in enabled_proxies]
                    
                    if missing_deps:
                        error_msg = (
                            f"Cannot enable {proxy_name}: missing proxy dependencies {missing_deps}. "
                            f"Enable those proxies first."
                        )
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    enabled_proxies.add(proxy_name)
                    results.append(f"Enabled proxy: {proxy_name}")
                    logger.info(f"Enabled proxy: {proxy_name}")
                    
                else:
                    # Check if any enabled petals depend on this proxy
                    dependent_petals = []
                    for petal, deps in petal_dependencies.items():
                        if petal in enabled_petals and proxy_name in deps:
                            dependent_petals.append(petal)
                    
                    # Check if any enabled proxies depend on this proxy
                    dependent_proxies = []
                    for proxy, deps in proxy_dependencies.items():
                        if proxy in enabled_proxies and proxy_name in deps:
                            dependent_proxies.append(proxy)
                    
                    if dependent_petals or dependent_proxies:
                        dependencies = []
                        if dependent_petals:
                            dependencies.append(f"petals {dependent_petals}")
                        if dependent_proxies:
                            dependencies.append(f"proxies {dependent_proxies}")
                        
                        error_msg = (
                            f"Cannot disable {proxy_name}: required by {' and '.join(dependencies)}. "
                            f"Disable those first."
                        )
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue
                    
                    enabled_proxies.discard(proxy_name)
                    results.append(f"Disabled proxy: {proxy_name}")
                    logger.info(f"Disabled proxy: {proxy_name}")
                    
            except Exception as e:
                error_msg = f"Error processing {proxy_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Update configuration
        config["enabled_proxies"] = list(enabled_proxies)
        
        # Write back to file
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        
        logger.info(f"Configuration updated with {len(results)} successful changes")
        
        response = {
            "success": len(results) > 0,
            "action": action,
            "processed_proxies": request.petals,  # Using petals field for proxy names
            "results": results,
            "restart_required": True,
            "message": f"Configuration updated. {len(results)} proxies {action.lower()}ed successfully."
        }
        
        if errors:
            response["errors"] = errors
            response["partial_success"] = len(results) > 0
        
        return response
        
    except Exception as e:
        logger.error(f"Error updating proxy configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )

