"""This computer's address on the local network.

A printed QR code has to carry an address a phone can open. ``http://localhost:5173``
is correct only on the computer running the app, so when nothing has been configured
the address is worked out here instead: the machine's address on the network it would
use to reach the outside world (no packet is actually sent, the socket only reveals
which interface would be chosen).

Settings still wins over this, and ``.env`` still wins over the guess, so a deployment
with a real domain is unaffected (D-119).
"""

from __future__ import annotations

import socket
from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

#: Addresses that no other device can open.
LOCAL_HOSTS = ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]")


def is_local_host(host: str) -> bool:
    name = host.lower().split(":")[0]
    return name in LOCAL_HOSTS or name.endswith(".localhost") or name.startswith("127.")


@lru_cache(maxsize=1)
def lan_address() -> str | None:
    """This computer's address on its own network, or None when there is no network."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.2)
            probe.connect(("192.0.2.1", 9))  # TEST-NET-1: routable, never answered
            address = str(probe.getsockname()[0])
    except OSError:
        return None
    return None if not address or is_local_host(address) else address


def reachable_base_url(configured: str) -> str:
    """Swap a localhost address for this computer's network address, port kept."""
    try:
        parts = urlsplit(configured)
    except ValueError:  # pragma: no cover - urlsplit is forgiving
        return configured
    if not parts.hostname or not is_local_host(parts.hostname):
        return configured
    address = lan_address()
    if address is None:
        return configured
    host = f"{address}:{parts.port}" if parts.port else address
    return urlunsplit((parts.scheme or "http", host, parts.path, parts.query, parts.fragment))


__all__ = ["is_local_host", "lan_address", "reachable_base_url"]
