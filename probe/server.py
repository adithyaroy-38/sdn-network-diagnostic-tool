import json
import os
import socket
import sys
import threading

# Let the script find config.py in the repo root, wherever it is run from
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ECHO_PORT


def handle(sock, data, addr):
    """Check one packet and echo it back unchanged."""
    try:
        msg = json.loads(data.decode("utf-8"))
        if not isinstance(msg, dict) or "seq" not in msg:
            raise ValueError("missing seq")
    except ValueError as e:
        print(f"[WARN] malformed packet from {addr}: {e}")
        return
    sock.sendto(data, addr)


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", ECHO_PORT))
    print(f"Echo server listening on UDP port {ECHO_PORT}", flush=True)
    try:
        while True:
            data, addr = sock.recvfrom(2048)
            threading.Thread(target=handle, args=(sock, data, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
