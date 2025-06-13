import importlib.metadata as md
from fastapi import FastAPI, APIRouter

from .decorators import action

def load_petals(app: FastAPI, proxies):
    for ep in md.entry_points(group="petal.plugins"):
        petal_cls = ep.load()
        petal     = petal_cls()
        petal.inject_proxies(proxies)

        router = APIRouter(prefix=f"/petals/{petal.name}")
        for attr in dir(petal):
            fn = getattr(petal, attr)
            meta = getattr(fn, "__petal_action__", None)
            if meta:
                router.add_api_route(
                    meta["path"], fn, methods=[meta["method"]]
                )
        app.include_router(router)
        app.logger.info("Mounted petal '%s' (%s)", petal.name, petal.version)