"""
Proxies for external services communication.
"""

from .localdb import LocalDBProxy
from .cloud import CloudDBProxy
from .bucket import S3BucketProxy
from .external import MavLinkExternalProxy, MavLinkFTPProxy
from .redis import RedisProxy

__all__ = ["LocalDBProxy", "CloudDBProxy", "S3BucketProxy", "MavLinkExternalProxy", "MavLinkFTPProxy"]
