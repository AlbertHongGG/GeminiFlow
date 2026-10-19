from __future__ import annotations
import time
import hashlib
from typing import Dict, Optional

class SAPISIDSigner:
    """
    Computes Google SAPISID authentication hash headers conforming to Google's 1P/3P SAPISIDHASH protocol.
    Used for WebChannel handshake and authenticated gateway calls.
    """
    DEFAULT_ORIGIN = "https://gemini.google.com"

    @classmethod
    def compute_hash(
        cls,
        sapisid: str,
        origin: str = DEFAULT_ORIGIN,
        timestamp: Optional[int] = None,
    ) -> str:
        if not sapisid:
            raise ValueError("SAPISID cookie value is required to compute SAPISIDHASH.")
        ts = int(time.time()) if timestamp is None else timestamp
        payload = f"{ts} {sapisid} {origin}"
        digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        token = f"{ts}_{digest}"
        return f"SAPISIDHASH {token} SAPISID1PHASH {token} SAPISID3PHASH {token}"

    @classmethod
    def get_authorization_header(
        cls,
        cookies: Dict[str, str],
        origin: str = DEFAULT_ORIGIN,
        timestamp: Optional[int] = None,
    ) -> str:
        sapisid = (
            cookies.get("SAPISID")
            or cookies.get("__Secure-3PAPISID")
            or cookies.get("__Secure-1PAPISID")
            or "placeholder_sapisid"
        )
        return cls.compute_hash(sapisid, origin=origin, timestamp=timestamp)
