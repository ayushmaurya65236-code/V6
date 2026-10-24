"""UDP discovery matching AURA LINK firmware (AURA_DISCOVER_V1)."""

from __future__ import annotations

import socket
import time

import config
from services.logger import log


def discover_esp32(
    timeout: float = 3.0,
    verbose: bool = True,
    port: int | None = None,
) -> str | None:
    port = port if port is not None else config.DISCOVERY_PORT
    if verbose:
        log.info("Scanning local network for ESP32...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.5)
    try:
        sock.bind(("", 0))
        sock.sendto(config.DISCOVERY_MESSAGE, ("255.255.255.255", port))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, address = sock.recvfrom(512)
            except socket.timeout:
                continue
            text = data.decode("utf-8", errors="ignore")
            if text.startswith(config.DISCOVERY_REPLY_PREFIX):
                ip = address[0]
                if verbose:
                    log.info("ESP32 FOUND -> IP: %s", ip)
                return ip
    except OSError as error:
        if verbose:
            log.warning("Discovery error: %s", error)
    finally:
        sock.close()
    return None
