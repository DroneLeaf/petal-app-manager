from fastapi import FastAPI
from .proxies import mavlink, ros, cloud, localdb, redis, external
from .plugins.loader import load_petals
from .api import health, proxy_info

def build_app() -> FastAPI:
    app = FastAPI(title="PetalAppManager")

    # ---------- start proxies ----------
    proxies = {
        # "mavlink": mavlink.MavLinkProxy("udp:127.0.0.1:14551"),
        "ext_mavlink": external.MavLinkExternalProxy("udp:127.0.0.1:14551"),
        # "ros"    : ros.ROSProxy(),
        # "cloud"  : cloud.CloudProxy(),
        "redis"  : redis.RedisProxy(),
        "db"     : localdb.LocalDBProxy(),
    }
    for p in proxies.values():
        app.add_event_handler("startup", p.start)
        app.add_event_handler("shutdown", p.stop)

    # ---------- core routers ----------
    app.include_router(health.router)
    app.include_router(proxy_info.router, prefix="/debug")

    # ---------- dynamic plugins ----------
    load_petals(app, proxies)

    return app


app = build_app()
