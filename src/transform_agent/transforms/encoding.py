"""
Encoding transforms: Base64, URL-encode, hex, UTF conversions.

All stdlib — sub-millisecond, zero dependencies.
"""

from __future__ import annotations

import base64
import urllib.parse


async def to_base64(data: bytes, options: dict | None = None) -> bytes:
    return base64.b64encode(data)


async def from_base64(data: bytes, options: dict | None = None) -> bytes:
    return base64.b64decode(data)


async def to_url_encoded(data: bytes, options: dict | None = None) -> bytes:
    return urllib.parse.quote(data.decode(), safe="").encode()


async def from_url_encoded(data: bytes, options: dict | None = None) -> bytes:
    return urllib.parse.unquote(data.decode()).encode()


async def to_hex(data: bytes, options: dict | None = None) -> bytes:
    return data.hex().encode()


async def from_hex(data: bytes, options: dict | None = None) -> bytes:
    return bytes.fromhex(data.decode().strip())
