from typing import Literal

def action(http: Literal["GET", "POST"], path: str):
    """
    Marks a petal method to be surfaced as an HTTP endpoint.
    """
    def wrapper(fn):
        fn.__petal_action__ = {"method": http, "path": path}
        return fn
    return wrapper
