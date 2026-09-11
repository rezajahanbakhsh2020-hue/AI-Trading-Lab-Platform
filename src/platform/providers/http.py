"""Bounded HTTP helpers for concrete providers.

Network access is explicit: callers must invoke these helpers. Importing this
module does not open connections. There are no retries or background reads.
"""

from typing import Any

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def read_limited(stream: Any, max_bytes: int = MAX_RESPONSE_BYTES) -> bytes:
    """Read a finite HTTP body. Never truncate silently.

    Raises ValueError if the payload exceeds max_bytes so callers cannot
    accidentally treat a partial body as complete market data.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    if stream is None:
        return b""

    read = getattr(stream, "read", None)
    if not callable(read):
        raise ValueError("HTTP stream does not support read()")

    try:
        data = read(max_bytes + 1)
    except TypeError:
        data = read()

    if data is None:
        return b""
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("HTTP body must be bytes")
    if len(data) > max_bytes:
        raise ValueError("HTTP response exceeded maximum allowed size")
    return bytes(data)
