import importlib.metadata as md
from fastapi import FastAPI, APIRouter
import logging

from ..proxies.base import BaseProxy
from typing import List
from ..plugins.base import Petal

from .decorators import action

logger = logging.getLogger("PluginsLoader")

def load_petals(app: FastAPI, proxies: List[BaseProxy]):
    for ep in md.entry_points(group="petal.plugins"):
        petal_cls    = ep.load()
        petal: Petal = petal_cls()
        petal.inject_proxies(proxies)

        router = APIRouter(
            prefix=f"/petals/{petal.name}",
            tags=[petal.name]  # This will group endpoints under the petal name in docs
        )
        for attr in dir(petal):
            fn = getattr(petal, attr)
            meta = getattr(fn, "__petal_action__", None)
            if meta:
                # Extract method and path
                method = meta.pop("method")
                path = meta.pop("path")
                
                # Pass all remaining parameters directly
                router.add_api_route(
                    path,
                    fn,
                    methods=[method],
                    **meta  # This will include response_model, status_code, responses, etc.
                )
        app.include_router(router)
        logger.info("Mounted petal '%s' (%s)", petal.name, petal.version)