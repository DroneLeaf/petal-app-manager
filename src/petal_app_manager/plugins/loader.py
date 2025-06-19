import importlib.metadata as md
from fastapi import FastAPI, APIRouter
import logging

from ..proxies.base import BaseProxy
from typing import List
from ..plugins.base import Petal

logger = logging.getLogger("PluginsLoader")

def load_petals(app: FastAPI, proxies: List[BaseProxy]):
    for ep in md.entry_points(group="petal.plugins"):
        petal_cls    = ep.load()
        petal: Petal = petal_cls()
        petal.inject_proxies(proxies)
        
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