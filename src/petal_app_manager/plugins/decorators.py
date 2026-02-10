from typing import Literal, Optional, Any, Dict

def http_action(method: Literal["GET", "POST"], path: str, **kwargs):
    """Marks a petal method as an HTTP endpoint."""
    def wrapper(fn):
        fn.__petal_action__ = {
            "protocol": "http",
            "method": method,
            "path": path,
            **kwargs
        }
        return fn
    return wrapper

def websocket_action(path: str, **kwargs):
    """Marks a petal method as a WebSocket endpoint."""
    def wrapper(fn):
        fn.__petal_action__ = {
            "protocol": "websocket",
            "path": path,
            **kwargs
        }
        return fn
    return wrapper

def mqtt_action(
    command: str,
    *,
    cpu_heavy: bool = False,
    **kwargs,
):
    """Marks a petal method as an MQTT command handler.

    The decorated method **must** be ``async def`` and accept
    ``(self, topic: str, message: dict)``—exactly the same signature
    that the legacy ``_command_handlers`` dict values have today.

    Parameters
    ----------
    command : str
        The *suffix* of the MQTT command, for example ``"mission_plan"``
        or ``"fetch_flight_records"``.  At runtime the framework prefixes
        the petal's ``name`` attribute automatically, producing
        ``"petal-leafsdk/mission_plan"`` etc.
    cpu_heavy : bool
        If ``True`` the entire handler invocation will be offloaded to the
        proxy's thread-pool executor so CPU-intensive work (e.g. NumPy)
        does not block the event loop.  Defaults to ``False``.
    """
    def wrapper(fn):
        fn.__mqtt_action__ = {
            "command": command,
            "cpu_heavy": cpu_heavy,
            **kwargs,
        }
        return fn
    return wrapper