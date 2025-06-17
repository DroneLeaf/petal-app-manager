# proxies/base.py
from abc import ABC, abstractmethod

class BaseProxy(ABC):
    @abstractmethod
    async def start(self): ...
    @abstractmethod
    async def stop(self): ...
