from io import BytesIO

import pytest

from src.platform.providers.http import MAX_RESPONSE_BYTES, read_limited


def test_read_limited_returns_full_body():
    assert read_limited(BytesIO(b"abc"), max_bytes=10) == b"abc"


def test_read_limited_rejects_oversized_body():
    with pytest.raises(ValueError, match="exceeded"):
        read_limited(BytesIO(b"abcdef"), max_bytes=3)


def test_read_limited_none_stream_is_empty():
    assert read_limited(None) == b""


def test_max_response_bytes_is_finite():
    assert isinstance(MAX_RESPONSE_BYTES, int)
    assert MAX_RESPONSE_BYTES > 0
