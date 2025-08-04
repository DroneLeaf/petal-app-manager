#!/usr/bin/env python3
import redis, traceback

SOCKET = "/var/run/redis/redis-server.sock"

try:
    r = redis.Redis(unix_socket_path=SOCKET)
    # this is the first CLIENT SETINFO that redis-py 6.x emits automatically
    r.execute_command("CLIENT", "SETINFO", "LIB-NAME", "redis-py")
except Exception:
    traceback.print_exc()
