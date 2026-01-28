from pathlib import Path

import yaml
import importlib.metadata as md
from importlib import import_module
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
import pathlib

from ..proxies.base import BaseProxy
from typing import List, Dict
from ..plugins.base import Petal

# Cache entry points once to avoid repeated scanning
_PETAL_EPS: Dict[str, md.EntryPoint] = {}
_EPS_CACHED = False

def _ensure_entry_points_cached():
    """Lazy load and cache entry points to avoid startup cost unless needed."""
    global _PETAL_EPS, _EPS_CACHED
    if not _EPS_CACHED:
        try:
            _PETAL_EPS = {ep.name: ep for ep in md.entry_points(group="petal.plugins")}
            _EPS_CACHED = True
        except Exception:
            # If entry points fail, just use empty dict
            _PETAL_EPS = {}
            _EPS_CACHED = True

def _load_class_from_path(path: str):
    """
    Load a class from 'module.submodule:ClassName'.
    Fast path that bypasses entry point discovery entirely.
    """
    module_name, _, attr = path.partition(":")
    if not module_name or not attr:
        raise ValueError(f"Invalid petal path {path!r}, expected 'module:Class'")
    
    module = import_module(module_name)
    return getattr(module, attr)

def _load_class_from_entry_point(name: str):
    """
    Load a class from entry points (legacy/third-party support).
    Only called if no direct path is configured.
    """
    _ensure_entry_points_cached()
    
    ep = _PETAL_EPS.get(name)
    if ep is None:
        raise RuntimeError(f"No entry point registered for petal '{name}' and no direct path configured")
    
    return ep.load()

def initialize_petals(
        petal_name_list: List[str],
        proxies: Dict[str, BaseProxy],
        logger: logging.Logger,
    ) -> List[Petal]:
    """
    Initialize petals without starting them up.
    Loads petal classes, instantiates them, and injects proxies.
    Does NOT call petal.startup().
    
    Returns a list of initialized (but not started) Petal objects.
    """
    from pathlib import Path
    from ..config import load_proxies_config

    # Load petal dependencies from proxies.yaml (auto-creates if missing)
    proxies_yaml_path = Path(__file__).parent.parent.parent.parent / "proxies.yaml"
    proxies_config = load_proxies_config(proxies_yaml_path)
    enabled_proxies = set(proxies_config.get("enabled_proxies") or [])
    petal_dependencies: Dict[str, list] = proxies_config.get("petal_dependencies", {}) or {}
    
    # New: direct import paths for fast loading
    petal_paths: Dict[str, str] = proxies_config.get("petals", {}) or {}

    petal_list: List[Petal] = []
    
    # Track loading method for statistics
    direct_loads = 0
    entry_point_loads = 0
    
    for name in petal_name_list:
        # Check required proxies for this petal from YAML
        required = set(petal_dependencies.get(name, []))
        missing_from_config = [proxy for proxy in required if proxy not in enabled_proxies]
        missing_from_runtime = [proxy for proxy in required if proxy not in proxies]

        if missing_from_config:
            logger.error(
                f"Cannot load {name} because it requires {', '.join(missing_from_config)} proxy/proxies and "
                f"{' and '.join(missing_from_config)} {'is' if len(missing_from_config)==1 else 'are'} turned off. "
                f"To turn on {name}, turn on the {', '.join(missing_from_config)} proxy/proxies."
            )
            continue  # Skip loading this petal

        if missing_from_runtime:
            logger.error(
                f"Cannot load {name} because it requires {', '.join(missing_from_runtime)} proxy/proxies but "
                f"{' and '.join(missing_from_runtime)} {'is' if len(missing_from_runtime)==1 else 'are'} not available at runtime."
            )
            continue  # Skip loading this petal

        # Try to load petal class - fast path first, entry points as fallback
        try:
            path = petal_paths.get(name)
            if path:
                # Fast path: direct import from configured path
                logger.debug(f"Loading petal '{name}' from direct path: {path}")
                petal_cls = _load_class_from_path(path)
                direct_loads += 1
            else:
                # Fallback: entry points (for third-party petals)
                logger.debug(f"Loading petal '{name}' from entry points (no direct path configured)")
                petal_cls = _load_class_from_entry_point(name)
                entry_point_loads += 1
                
        except Exception as e:
            logger.error(f"Failed to load petal '{name}': {e}")
            continue

        # Initialize and configure the petal (but don't start it)
        try:
            petal: Petal = petal_cls()
            petal.inject_proxies(proxies)
            petal_list.append(petal)
            logger.info(f"Initialized petal '{name}' (version: {getattr(petal, 'version', 'unknown')})")
        except Exception as e:
            logger.error(f"Failed to initialize petal '{name}': {e}")
            continue

    # Log loading statistics
    total_initialized = len(petal_list)
    if total_initialized > 0:
        logger.info(f"Initialized {total_initialized} petals total:")
        if direct_loads > 0:
            logger.info(f"  - {direct_loads} via direct path (fast)")
        if entry_point_loads > 0:
            logger.info(f"  - {entry_point_loads} via entry points (fallback)")
    else:
        logger.warning("No petals initialized; ensure plugins are installed and configured correctly")
        
    return petal_list


def startup_petals(
        app: FastAPI,
        petal_list: List[Petal],
        logger: logging.Logger,
    ) -> List[Petal]:
    """
    Start up initialized petals and mount them to the FastAPI app.
    Calls petal.startup() and mounts static files, templates, and routers.
    
    Returns the list of successfully started petals.
    """
    started_petals: List[Petal] = []
    
    for petal in petal_list:
        # Start up the petal
        try:
            petal.startup()
            started_petals.append(petal)
            logger.info(f"Started petal '{petal.name}' (version: {getattr(petal, 'version', 'unknown')})")
        except Exception as e:
            logger.error(f"Failed to start petal '{petal.name}': {e}")
            continue

        # Mount static files for this plugin
        if getattr(petal, "static_dir", False):
            root_dir = pathlib.Path(__file__).parent.parent.parent.parent
            # construct the static directory path
            # assuming static files are in a 'static' directory and the petals static files are under
            # 'static/petals/<petal_name>'
            static_dir = root_dir / "static" / petal.name
            if not static_dir.exists():
                logger.warning("Static directory '%s' for petal '%s' does not exist; skipping static mount", static_dir, petal.name)
                static_dir = None
            else:
                logger.info("Mounting static files for petal '%s' at '%s'", petal.name, static_dir)
                app.mount(f"/static/{petal.name}", StaticFiles(directory=static_dir), name=f"{petal.name}_static")

        if getattr(petal, "template_dir", False):
            # Assuming templates are in a 'templates' directory under the petal's root
            templates_dir = pathlib.Path(__file__).parent.parent.parent.parent / "templates" / petal.name
            if not templates_dir.exists():
                logger.warning("Templates directory '%s' for petal '%s' does not exist; skipping template mount", templates_dir, petal.name)
            else:
                logger.info("Injecting templates for petal '%s' at '%s'", petal.name, templates_dir)
                templates = Jinja2Templates(directory=templates_dir)
                petal.inject_templates({"default": templates})

        router = APIRouter(
            prefix=f"/petals/{petal.name}",
            tags=[petal.name]
        )
        for attr in dir(petal):
            fn = getattr(petal, attr)
            meta = getattr(fn, "__petal_action__", None)
            if not meta:
                continue
            protocol = meta.get("protocol", None)
            if not protocol:
                logger.warning("Petal '%s' has method '%s' without protocol metadata; skipping", petal.name, attr)
                continue
            if protocol not in ["http", "websocket", "mqtt"]:
                logger.warning("Petal '%s' has method '%s' with unsupported protocol '%s'; skipping", petal.name, attr, protocol)
                continue
            if protocol == "http":
                router.add_api_route(
                    meta["path"],
                    fn,
                    methods=[meta["method"]],
                    **{k: v for k, v in meta.items() if k not in ["protocol", "method", "path", "tags"]}
                )
            elif protocol == "websocket":
                router.add_api_websocket_route(
                    meta["path"],
                    fn,
                    **{k: v for k, v in meta.items() if k not in ["protocol", "path"]}
                )
            elif protocol == "mqtt":
            # Register with MQTT broker when implemented
                pass
            # Additional protocols can be added here
                
        app.include_router(router)

    if started_petals:
        logger.info(f"Successfully started {len(started_petals)} petals")
    else:
        logger.warning("No petals started successfully")
        
    return started_petals


def load_petals(
        app: FastAPI, 
        petal_name_list: List[str],
        proxies: Dict[str, BaseProxy],
        logger: logging.Logger,
    ) -> List[Petal]:
    """
    Load, initialize, and start petals (convenience function).
    This is a wrapper that calls initialize_petals() and startup_petals().
    
    For more control over the initialization and startup process,
    use initialize_petals() and startup_petals() separately.
    """
    petal_list = initialize_petals(petal_name_list, proxies, logger)
    started_petals = startup_petals(app, petal_list, logger)
    return started_petals