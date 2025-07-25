from typing import Dict, Any, Optional

# Global proxy references - these will be set by the main application
_proxies: Dict[str, Any] = {}

def set_proxies(proxies: Dict[str, Any]):
    """Set the proxy instances for api endpoints."""
    global _proxies
    _proxies = proxies

def get_proxies() -> Dict[str, Any]:
    """Get the proxy instances."""
    return _proxies