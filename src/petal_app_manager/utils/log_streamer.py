import logging
import json
from collections import deque
from datetime import datetime
from typing import Dict, Any, Optional, Set
import threading
import asyncio

class LogStreamer:
    """Captures and streams logs for real-time display"""
    
    def __init__(self, max_logs: int = 1000):
        self.max_logs = max_logs
        self.logs = deque(maxlen=max_logs)
        self.subscribers: Set[asyncio.Queue] = set()
        self.lock = threading.Lock()
        
    def add_log(self, record: logging.LogRecord):
        """Add a log record to the stream"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": getattr(record, 'module', ''),
            "funcName": getattr(record, 'funcName', ''),
            "lineno": getattr(record, 'lineno', 0)
        }
        
        with self.lock:
            self.logs.append(log_entry)
            
        # Notify subscribers
        self._notify_subscribers(log_entry)
    
    def _notify_subscribers(self, log_entry: Dict[str, Any]):
        """Notify all subscribers of new log entry"""
        dead_subscribers = set()
        for subscriber in self.subscribers.copy():
            try:
                # Use put_nowait to avoid blocking
                subscriber.put_nowait(log_entry)
            except Exception:
                dead_subscribers.add(subscriber)
        
        # Clean up dead subscribers
        with self.lock:
            self.subscribers -= dead_subscribers
    
    def get_recent_logs(self, count: Optional[int] = None) -> list:
        """Get recent logs"""
        with self.lock:
            if count is None:
                return list(self.logs)
            return list(self.logs)[-count:]
    
    def subscribe(self, queue: asyncio.Queue):
        """Subscribe to log updates"""
        with self.lock:
            self.subscribers.add(queue)
    
    def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from log updates"""
        with self.lock:
            self.subscribers.discard(queue)

# Global log streamer instance
log_streamer = LogStreamer()

class StreamingLogHandler(logging.Handler):
    """Custom log handler that streams to the LogStreamer"""
    
    def __init__(self, streamer: LogStreamer):
        super().__init__()
        self.streamer = streamer
        
    def emit(self, record):
        try:
            self.streamer.add_log(record)
        except Exception:
            self.handleError(record)
