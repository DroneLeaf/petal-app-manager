from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import yaml
from pathlib import Path
from pydantic import BaseModel
import logging
import json
import asyncio
import importlib.metadata as md

# Import log streaming functionality
from ..utils.log_streamer import log_streamer
# Import config utilities
from ..config import load_proxies_config

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

class PetalInfo(BaseModel):
    name: str
    enabled: bool
    dependencies: List[str]

class ProxyInfo(BaseModel):
    name: str
    enabled: bool
    dependencies: List[str]
    dependents: List[str]  # Proxies and petals that depend on this proxy

class AllComponentsResponse(BaseModel):
    petals: List[PetalInfo]
    proxies: List[ProxyInfo]
    total_petals: int
    total_proxies: int

@router.get("/status")
async def get_status() -> ConfigResponse:
    """Get current configuration status"""
    logger = get_logger()
    logger.debug("Processing status request")
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        config = load_proxies_config(config_path)
        
        logger.debug(f"Successfully loaded configuration from {config_path}")
        logger.info("Retrieved current configuration status")
        
        return ConfigResponse(
            enabled_proxies=config.get("enabled_proxies", []),
            enabled_petals=config.get("enabled_petals", []),
            petal_dependencies=config.get("petal_dependencies", {}),
            proxy_dependencies=config.get("proxy_dependencies", {})
        )
    except Exception as e:
        logger.error(f"Error reading configuration: {e}")
        logger.debug(f"Configuration error details: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error reading configuration: {str(e)}"
        )

@router.post("/petals/control")
async def control_petals(request: PetalControlRequest) -> Dict[str, Any]:
    """Enable or disable one or more petals"""
    logger = get_logger()
    logger.debug(f"Received petals control request: action='{request.action}', petals={request.petals}")
    
    # Validate action
    if request.action.upper() not in ["ON", "OFF"]:
        logger.error(f"Invalid action '{request.action}' provided. Expected 'ON' or 'OFF'")
        raise HTTPException(
            status_code=400,
            detail="Action must be either 'ON' or 'OFF'"
        )
    
    # Validate petals list
    if not request.petals:
        logger.error("Empty petals list provided in request")
        raise HTTPException(
            status_code=400,
            detail="At least one petal name must be provided"
        )
    
    action = request.action.upper()
    enable_petals = action == "ON"
    logger.info(f"Processing {action} action for {len(request.petals)} petals: {request.petals}")
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        logger.debug(f"Loading configuration from: {config_path}")
        
        # Read current configuration (auto-creates if missing)
        config = load_proxies_config(config_path)
        
        enabled_petals = set(config.get("enabled_petals", []) or [])
        enabled_proxies = set(config.get("enabled_proxies", []) or [])
        petal_dependencies = config.get("petal_dependencies", {})
        
        logger.debug(f"Current enabled petals: {list(enabled_petals)}")
        logger.debug(f"Current enabled proxies: {list(enabled_proxies)}")
        logger.debug(f"Petal dependencies: {petal_dependencies}")
        
        results = []
        errors = []
        
        for petal_name in request.petals:
            logger.debug(f"Processing petal: {petal_name}")
            try:
                if enable_petals:
                    logger.debug(f"Attempting to enable petal: {petal_name}")
                    # Check if dependencies are met before enabling
                    required_deps = petal_dependencies.get(petal_name, [])
                    logger.debug(f"Petal {petal_name} requires dependencies: {required_deps}")
                    missing_deps = [dep for dep in required_deps if dep not in enabled_proxies]
                    
                    if missing_deps:
                        error_msg = (
                            f"Cannot enable {petal_name}: missing dependencies {missing_deps}. "
                            f"Enable those proxies first."
                        )
                        errors.append(error_msg)
                        logger.error(f"DEPENDENCY ERROR: {error_msg}")
                        continue
                    
                    if petal_name in enabled_petals:
                        logger.debug(f"Petal {petal_name} is already enabled, skipping")
                    else:
                        enabled_petals.add(petal_name)
                        results.append(f"Enabled petal: {petal_name}")
                        logger.info(f"Successfully enabled petal: {petal_name}")
                    
                else:
                    logger.debug(f"Attempting to disable petal: {petal_name}")
                    # Disable petal
                    if petal_name in enabled_petals:
                        enabled_petals.discard(petal_name)
                        results.append(f"Disabled petal: {petal_name}")
                        logger.info(f"Successfully disabled petal: {petal_name}")
                    else:
                        logger.debug(f"Petal {petal_name} was already disabled, skipping")
                    
            except Exception as e:
                error_msg = f"Error processing {petal_name}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"PROCESSING ERROR: {error_msg}")
                logger.debug(f"Exception details for {petal_name}: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Update configuration
        config["enabled_petals"] = list(enabled_petals)
        logger.debug(f"Updated enabled petals: {list(enabled_petals)}")
        
        # Write back to file
        logger.debug(f"Writing configuration back to: {config_path}")
        with open(config_path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False)
        
        logger.info(f"Configuration updated successfully with {len(results)} changes")
        if errors:
            logger.warning(f"Request completed with {len(errors)} errors: {errors}")

        if enable_petals:
            success = all(p in enabled_petals for p in request.petals)
        else:
            success = all(p not in enabled_petals for p in request.petals)

        response = {
            "success": success,
            "action": action,
            "processed_petals": request.petals,
            "results": results,
            "message": f"Configuration updated. {len(results)} petals switched {action.lower()} successfully."
        }
        
        if errors:
            response["errors"] = errors
            response["partial_success"] = len(results) > 0
        
        logger.debug(f"Returning response: {response}")
        return response
        
    except Exception as e:
        logger.critical(f"CRITICAL ERROR updating petal configuration: {e}")
        logger.debug(f"Critical error details: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )

@router.post("/proxies/control")
async def control_proxies(request: PetalControlRequest) -> Dict[str, Any]:
    """Enable or disable one or more proxies"""
    logger = get_logger()
    logger.debug(f"Received proxies control request: action='{request.action}', proxies={request.petals}")
    
    # Validate action
    if request.action.upper() not in ["ON", "OFF"]:
        logger.error(f"Invalid action '{request.action}' provided. Expected 'ON' or 'OFF'")
        raise HTTPException(
            status_code=400,
            detail="Action must be either 'ON' or 'OFF'"
        )
    
    logger.info(f"Processing {request.action.upper()} action for {len(request.petals)} proxies: {request.petals}")
    
    # Validate proxies list (reusing petals field name for consistency)
    if not request.petals:
        logger.error("Empty proxies list provided in request")
        raise HTTPException(
            status_code=400,
            detail="At least one proxy name must be provided"
        )
    
    action = request.action.upper()
    enable_proxies = action == "ON"
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        logger.debug(f"Loading configuration from: {config_path}")
        
        # Read current configuration (auto-creates if missing)
        config = load_proxies_config(config_path)
        
        enabled_proxies = set(config.get("enabled_proxies", []) or [])
        enabled_petals = set(config.get("enabled_petals", []) or [])
        petal_dependencies = config.get("petal_dependencies", {})
        proxy_dependencies = config.get("proxy_dependencies", {})
        
        logger.debug(f"Current enabled proxies: {list(enabled_proxies)}")
        logger.debug(f"Current enabled petals: {list(enabled_petals)}")
        logger.debug(f"Proxy dependencies: {proxy_dependencies}")
        
        results = []
        errors = []
        
        for proxy_name in request.petals:  # Using petals field for proxy names
            logger.debug(f"Processing proxy: {proxy_name}")
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
                        logger.error(f"PROXY DEPENDENCY ERROR: {error_msg}")
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
            "message": f"Configuration updated. {len(results)} proxies switched {action.lower()} successfully."
        }
        
        if errors:
            response["errors"] = errors
            response["partial_success"] = len(results) > 0
        
        return response
        
    except Exception as e:
        logger.critical(f"CRITICAL ERROR updating proxy configuration: {e}")
        logger.debug(f"Critical error details: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update configuration: {str(e)}"
        )

@router.get("/components/list", response_model=AllComponentsResponse)
async def list_all_components():
    """List all available petals and proxies, regardless of their enabled/disabled state"""
    logger = get_logger()
    logger.debug("Processing components list request")
    
    try:
        config_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
        logger.debug(f"Loading configuration from: {config_path}")
        config = load_proxies_config(config_path)
        
        enabled_proxies = set(config.get("enabled_proxies", []) or [])
        enabled_petals = set(config.get("enabled_petals", []) or [])
        petal_dependencies = config.get("petal_dependencies", {})
        proxy_dependencies = config.get("proxy_dependencies", {})
        
        logger.debug(f"Configuration loaded - enabled proxies: {list(enabled_proxies)}, enabled petals: {list(enabled_petals)}")
        
        # Discover all available petals from entry points
        available_petals = []
        discovered_petal_names = set()
        
        try:
            logger.debug("Discovering petals from entry points...")
            entry_points = list(md.entry_points(group="petal.plugins"))
            logger.debug(f"Found {len(entry_points)} petal entry points")
            
            for ep in entry_points:
                # Skip if we've already processed this petal name
                if ep.name in discovered_petal_names:
                    logger.debug(f"Skipping duplicate entry point for petal: {ep.name}")
                    continue
                
                logger.debug(f"Processing petal: {ep.name} (enabled: {ep.name in enabled_petals})")
                petal_info = PetalInfo(
                    name=ep.name,
                    enabled=ep.name in enabled_petals,
                    dependencies=petal_dependencies.get(ep.name, [])
                )
                available_petals.append(petal_info)
                discovered_petal_names.add(ep.name)
        except Exception as e:
            logger.warning(f"Error discovering petals from entry points: {e}")
            logger.debug(f"Petal discovery error details: {type(e).__name__}: {str(e)}", exc_info=True)
        
        # Add any petals from configuration that weren't discovered via entry_points
        for petal_name in petal_dependencies.keys():
            if petal_name not in discovered_petal_names:
                petal_info = PetalInfo(
                    name=petal_name,
                    enabled=petal_name in enabled_petals,
                    dependencies=petal_dependencies.get(petal_name, [])
                )
                available_petals.append(petal_info)
                discovered_petal_names.add(petal_name)
        
        # Also add any enabled petals that might not be in dependencies
        for petal_name in enabled_petals:
            if petal_name not in discovered_petal_names:
                petal_info = PetalInfo(
                    name=petal_name,
                    enabled=True,
                    dependencies=petal_dependencies.get(petal_name, [])
                )
                available_petals.append(petal_info)
                discovered_petal_names.add(petal_name)
        
        # Define all known proxy types
        # This is based on the proxy types defined in main.py
        known_proxy_types = [
            "ext_mavlink",
            "redis", 
            "db",
            "cloud",
            "bucket",
            "ftp_mavlink"
        ]
        
        # Build proxy info with dependencies and dependents
        available_proxies = []
        for proxy_name in known_proxy_types:
            # Find what depends on this proxy
            dependents = []
            
            # Check petals that depend on this proxy
            for petal, deps in petal_dependencies.items():
                if proxy_name in deps:
                    dependents.append(f"petal:{petal}")
            
            # Check proxies that depend on this proxy
            for proxy, deps in proxy_dependencies.items():
                if proxy_name in deps:
                    dependents.append(f"proxy:{proxy}")
            
            proxy_info = ProxyInfo(
                name=proxy_name,
                enabled=proxy_name in enabled_proxies,
                dependencies=proxy_dependencies.get(proxy_name, []),
                dependents=dependents
            )
            available_proxies.append(proxy_info)
        
        # Add any additional proxies from configuration that aren't in known types
        for proxy_name in enabled_proxies:
            if proxy_name not in known_proxy_types:
                # Find dependents for unknown proxy
                dependents = []
                for petal, deps in petal_dependencies.items():
                    if proxy_name in deps:
                        dependents.append(f"petal:{petal}")
                for proxy, deps in proxy_dependencies.items():
                    if proxy_name in deps:
                        dependents.append(f"proxy:{proxy}")
                
                proxy_info = ProxyInfo(
                    name=proxy_name,
                    enabled=True,  # It's in enabled_proxies
                    dependencies=proxy_dependencies.get(proxy_name, []),
                    dependents=dependents
                )
                available_proxies.append(proxy_info)
        
        # Sort by name for consistent ordering
        available_petals.sort(key=lambda x: x.name)
        available_proxies.sort(key=lambda x: x.name)
        
        # Count enabled components for more informative logging
        enabled_petal_count = len([p for p in available_petals if p.enabled])
        enabled_proxy_count = len([p for p in available_proxies if p.enabled])
        
        logger.info(f"Listed {len(available_petals)} petals ({enabled_petal_count} enabled) and {len(available_proxies)} proxies ({enabled_proxy_count} enabled)")
        
        return AllComponentsResponse(
            petals=available_petals,
            proxies=available_proxies,
            total_petals=len(available_petals),
            total_proxies=len(available_proxies)
        )
        
    except Exception as e:
        logger.error(f"Error listing components: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list components: {str(e)}"
        )

@router.get("/logs/recent")
async def get_recent_logs(count: Optional[int] = 100) -> Dict[str, Any]:
    """Get recent log entries"""
    logger = get_logger()
    
    try:
        logs = log_streamer.get_recent_logs(count)
        return {
            "logs": logs,
            "total_count": len(logs),
            "max_logs": log_streamer.max_logs
        }
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recent logs: {str(e)}"
        )

@router.get("/logs/stream")
async def stream_logs():
    """Stream logs in real-time using Server-Sent Events"""
    
    async def log_generator():
        queue = asyncio.Queue()
        log_streamer.subscribe(queue)
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connection', 'message': 'Connected to log stream'})}\n\n"
            
            while True:
                try:
                    # Wait for new log entry
                    log_entry = await asyncio.wait_for(queue.get(), timeout=30.0)
                    log_entry['type'] = 'log'
                    yield f"data: {json.dumps(log_entry)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'keepalive', 'timestamp': ''})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    break
        finally:
            log_streamer.unsubscribe(queue)
    
    return StreamingResponse(
        log_generator(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )

