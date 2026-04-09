#!/usr/bin/env python3
"""
Simple syslog forwarder - receives UDP syslog and forwards to backend API.
"""

import socket
import json
import os
import threading
import logging
import requests
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
SYSLOG_HOST = os.getenv("SYSLOG_HOST", "0.0.0.0")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", 514))
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api/syslog/ingest")
API_KEY = os.getenv("API_KEY", "syslog-secret-key")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
BATCH_TIMEOUT = int(os.getenv("BATCH_TIMEOUT", 5))

# Buffer for batching
message_buffer = []
buffer_lock = threading.Lock()
last_flush = datetime.now()


def parse_syslog(message: str) -> dict:
    """Parse syslog message and extract fields."""
    try:
        # Try to parse as RFC 3164 or RFC 5424
        # Format: <priority>version hostname app-name pid msg

        parts = message.split(None, 4)  # Split into max 5 parts

        if len(parts) >= 1 and parts[0].startswith("<"):
            priority = int(parts[0][1:].split(">")[0])
            facility = priority >> 3
            severity = priority & 7

            if len(parts) >= 5:
                # RFC 5424 format
                return {
                    "device_ip": parts[2] if len(parts) > 2 else "unknown",
                    "program": parts[3] if len(parts) > 3 else "syslog",
                    "message": parts[4],
                    "facility": facility,
                    "severity": severity,
                    "received_at": datetime.utcnow().isoformat() + "Z",
                }
            elif len(parts) >= 2:
                # Likely RFC 3164
                return {
                    "device_ip": parts[1] if len(parts) > 1 else "unknown",
                    "program": parts[0],
                    "message": message,
                    "facility": facility,
                    "severity": severity,
                    "received_at": datetime.utcnow().isoformat() + "Z",
                }

        # Fallback - treat whole message
        return {
            "device_ip": "unknown",
            "program": "syslog",
            "message": message,
            "facility": 1,  # user-level
            "severity": 6,  # informational
            "received_at": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        logger.warning(f"Failed to parse syslog: {e}")
        return {
            "device_ip": "unknown",
            "program": "syslog",
            "message": message,
            "facility": 1,
            "severity": 6,
            "received_at": datetime.utcnow().isoformat() + "Z",
        }


def flush_buffer():
    """Flush the message buffer to the backend."""
    global message_buffer, last_flush

    with buffer_lock:
        if not message_buffer:
            return

        to_send = message_buffer.copy()
        message_buffer.clear()
        last_flush = datetime.now()

    if to_send:
        try:
            headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}
            logger.info(f"Sending {len(to_send)} messages to {BACKEND_URL}")
            response = requests.post(
                BACKEND_URL, json=to_send, headers=headers, timeout=10
            )
            logger.info(
                f"Backend response: {response.status_code} - {response.text[:200]}"
            )
            if response.status_code in (200, 201):
                logger.info(f"Forwarded {len(to_send)} messages to backend")
            else:
                logger.warning(
                    f"Backend returned {response.status_code}: {response.text}"
                )
                # Put messages back in buffer
                with buffer_lock:
                    message_buffer.extend(to_send)
        except Exception as e:
            logger.error(f"Failed to forward messages: {e}")
            # Put messages back in buffer
            with buffer_lock:
                message_buffer.extend(to_send)


def flush_worker():
    """Periodically flush the buffer."""
    while True:
        import time

        time.sleep(BATCH_TIMEOUT)

        with buffer_lock:
            should_flush = len(message_buffer) >= BATCH_SIZE

        if should_flush:
            flush_buffer()


def handle_client(data, addr):
    """Handle incoming syslog message."""
    try:
        message = data.decode("utf-8", errors="replace").strip()
        if not message:
            return

        parsed = parse_syslog(message)
        logger.info(f"Received from {addr}: {message[:50]}...")

        with buffer_lock:
            message_buffer.append(parsed)

        # Flush immediately (outside lock to avoid deadlock)
        if len(message_buffer) >= 1:
            flush_buffer()

    except Exception as e:
        logger.error(f"Error handling message from {addr}: {e}")


def main():
    logger.info(f"Starting syslog forwarder on {SYSLOG_HOST}:{SYSLOG_PORT}")
    logger.info(f"Forwarding to {BACKEND_URL}")

    # Start flush worker
    flush_thread = threading.Thread(target=flush_worker, daemon=True)
    flush_thread.start()

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((SYSLOG_HOST, SYSLOG_PORT))

    logger.info(f"Listening on {SYSLOG_HOST}:{SYSLOG_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            handle_client(data, addr)
        except Exception as e:
            logger.error(f"Error receiving data: {e}")


if __name__ == "__main__":
    main()
