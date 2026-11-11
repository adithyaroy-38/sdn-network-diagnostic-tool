"""
Concurrent UDP Echo Server
SDN Network Diagnostic and Path Analysis Tool

Listens for UDP probes on port 9999 and echoes
valid JSON messages back to their original sender.
"""

import json
import socket
import threading
import os
import sys
from concurrent.futures import ThreadPoolExecutor

# Add the project root so config.py can be imported.
PROJECT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
sys.path.insert(0, PROJECT_DIR)

from config import ECHO_PORT


# Server configuration
SERVER_IP = "0.0.0.0"
MAX_PACKET_SIZE = 2048
MAX_WORKERS = 32

# Lock prevents simultaneous log messages from mixing.
print_lock = threading.Lock()


def log(message):
    """Print a thread-safe server message."""
    with print_lock:
        print(message, flush=True)


def handle_packet(server_socket, data, address):
    """Validate and echo one UDP packet."""

    try:
        # Reject oversized messages.
        if len(data) > MAX_PACKET_SIZE:
            log(f"[REJECTED] Oversized packet from {address}")
            return

        # Decode JSON.
        message = json.loads(data.decode("utf-8"))

        # Validate required fields.
        if not isinstance(message, dict):
            raise ValueError("Message must be a JSON object")

        if not isinstance(message.get("seq"), int):
            raise ValueError("Missing or invalid sequence number")

        if not isinstance(message.get("ts_send"), (int, float)):
            raise ValueError("Missing or invalid timestamp")

        if not isinstance(message.get("src"), str):
            raise ValueError("Missing or invalid source")

        if not isinstance(message.get("dst"), str):
            raise ValueError("Missing or invalid destination")

        # Echo the original payload unchanged.
        server_socket.sendto(data, address)

        log(
            f"[ECHO] {message['src']} -> {message['dst']} "
            f"| Sequence: {message['seq']} "
            f"| Client: {address}"
        )

    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        log(f"[REJECTED] Invalid packet from {address}: {error}")

    except OSError as error:
        log(f"[ERROR] Could not send response to {address}: {error}")


def start_server():
    """Start the concurrent UDP echo server."""

    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    server_socket.bind((SERVER_IP, ECHO_PORT))

    log("=" * 50)
    log("UDP ECHO SERVER STARTED")
    log(f"Listening on {SERVER_IP}:{ECHO_PORT}")
    log(f"Maximum concurrent workers: {MAX_WORKERS}")
    log("=" * 50)

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:

            while True:
                try:
                    data, address = server_socket.recvfrom(
                        MAX_PACKET_SIZE + 1
                    )

                    # Process packets concurrently.
                    executor.submit(
                        handle_packet,
                        server_socket,
                        data,
                        address
                    )

                except OSError as error:
                    log(f"[ERROR] Socket error: {error}")

    except KeyboardInterrupt:
        log("\n[STOPPING] UDP echo server shutting down.")

    finally:
        server_socket.close()
        log("[STOPPED] UDP echo server closed.")


if __name__ == "__main__":
    start_server()
