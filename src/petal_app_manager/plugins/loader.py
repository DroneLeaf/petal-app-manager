import importlib.metadata as md
from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging
import os
import pathlib

from ..proxies.base import BaseProxy
from typing import List
from ..plugins.base import Petal

def load_petals(app: FastAPI, proxies: List[BaseProxy], logger: logging.Logger) -> List[Petal]:
    petal_list = []
    for ep in md.entry_points(group="petal.plugins"):
        petal_cls    = ep.load()
        petal: Petal = petal_cls()
        petal.inject_proxies(proxies)
        petal.startup()

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
        logger.info("Mounted petal '%s' (%s)", petal.name, petal.version)

        petal_list.append(petal)

    logger.info("Loaded %d petals", len(petal_list))
    if not petal_list:
        logger.warning("No petals loaded; ensure plugins are installed and configured correctly")
    return petal_list