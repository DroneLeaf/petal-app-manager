"""
Proxies for external services communication.
"""

from .localdb import LocalDBProxy
from .cloud import CloudDBProxy
from .external import MavLinkExternalProxy, MavLinkFTPProxy
from .redis import RedisProxy

__all__ = ["LocalDBProxy", "CloudDBProxy", "MavLinkExternalProxy", "MavLinkFTPProxy"]
