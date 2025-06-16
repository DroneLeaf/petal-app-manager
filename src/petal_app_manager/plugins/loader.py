import importlib.metadata as md
from fastapi import FastAPI, APIRouter
import logging

from .decorators import action

logger = logging.getLogger("PluginsLoader")

def load_petals(app: FastAPI, proxies):
    for ep in md.entry_points(group="petal.plugins"):
        petal_cls = ep.load()
        petal     = petal_cls()
        petal.inject_proxies(proxies)

        router = APIRouter(
            prefix=f"/petals/{petal.name}",
            tags=[petal.name]  # This will group endpoints under the petal name in docs
        )
        for attr in dir(petal):
            fn = getattr(petal, attr)
            meta = getattr(fn, "__petal_action__", None)
            if meta:
                router.add_api_route(
                    meta["path"], fn, methods=[meta["method"]]
                )
        app.include_router(router)
        logger.info("Mounted petal '%s' (%s)", petal.name, petal.version)