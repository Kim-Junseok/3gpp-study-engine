"""Run Python regression checks with all Internet socket connections denied."""
from __future__ import annotations

import socket
import sys

import pytest


def main():
    attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def blocked(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(str(address))
            raise RuntimeError("Internet sockets disabled during Stage A verification")
        return original_connect(self, address)

    def blocked_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            attempts.append(str(address))
            raise RuntimeError("Internet sockets disabled during Stage A verification")
        return original_connect_ex(self, address)

    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked_ex
    try:
        code = pytest.main(["-p", "no:cacheprovider", "-m", "not integration", *sys.argv[1:]])
    finally:
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
    print(f"Internet socket connection attempts: {len(attempts)}")
    return int(code) if code else (1 if attempts else 0)


if __name__ == "__main__":
    raise SystemExit(main())
