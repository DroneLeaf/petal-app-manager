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

def mqtt_action(topic: str, **kwargs):
    """Marks a petal method as an MQTT handler."""
    def wrapper(fn):
        fn.__petal_action__ = {
            "protocol": "mqtt",
            "topic": topic,
            **kwargs
        }
        return fn
    return wrapper