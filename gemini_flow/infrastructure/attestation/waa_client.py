import json
import logging
import time
from typing import Optional, Tuple
from curl_cffi.requests import AsyncSession
from ...domain.exceptions import ChallengeFetchError

logger = logging.getLogger(__name__)

WAA_CREATE_URL = "https://waa-pa.clients6.google.com/$rpc/google.internal.waa.v1.Waa/Create"
WAA_API_KEY = "AIzaSyBGb5fGAyC-pRcRU6MUHb__b_vKha71HRE"
GEMINI_WAA_SERVICE_KEY = "br1aemAN9owlYRs9NnsA"

class WaaClient:
    """
    Client for Google's Web Attestation API (WAA).
    Responsible for fetching and caching ephemeral Botguard challenges and VM scripts.
    """

    def __init__(
        self,
        cache_ttl_seconds: float = 600.0,
        proxy: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self._cache_ttl = cache_ttl_seconds
        self._proxy = proxy
        self._timeout = timeout
        self._cached_bytecode: Optional[str] = None
        self._cached_script_code: Optional[str] = None
        self._cached_at: float = 0.0

    @property
    def is_cache_valid(self) -> bool:
        return (
            bool(self._cached_bytecode)
            and bool(self._cached_script_code)
            and (time.time() - self._cached_at < self._cache_ttl)
        )

    async def get_challenge(self) -> Tuple[str, str]:
        """
        Returns (bytecode, script_code).
        Uses cached challenge if valid, otherwise fetches a fresh challenge from Google WAA.
        """
        if self.is_cache_valid:
            return self._cached_bytecode, self._cached_script_code

        bytecode, script_code = await self._fetch_fresh_challenge()
        self._cached_bytecode = bytecode
        self._cached_script_code = script_code
        self._cached_at = time.time()
        logger.debug("Successfully fetched and cached fresh Botguard challenge (TTL: %.0fs)", self._cache_ttl)
        return bytecode, script_code

    async def _fetch_fresh_challenge(self) -> Tuple[str, str]:
        headers = {
            "content-type": "application/json+protobuf",
            "x-goog-api-key": WAA_API_KEY,
        }
        body = json.dumps([GEMINI_WAA_SERVICE_KEY])

        try:
            async with AsyncSession(
                impersonate="chrome120",
                proxy=self._proxy,
                timeout=self._timeout,
            ) as session:
                resp = await session.post(
                    WAA_CREATE_URL,
                    data=body.encode("utf-8"),
                    headers=headers
                )
                if resp.status_code != 200:
                    raise ChallengeFetchError(
                        f"WAA Create returned HTTP {resp.status_code}: {resp.text[:200]}"
                    )

                data = json.loads(resp.text)
                if not data or not isinstance(data, list) or len(data) == 0:
                    raise ChallengeFetchError(f"Unexpected WAA response format: {resp.text[:200]}")

                challenge = data[0]
                if len(challenge) < 5 or not challenge[4]:
                    raise ChallengeFetchError(f"Invalid challenge payload from WAA: {resp.text[:200]}")

                bytecode = challenge[4]
                script_path = challenge[2][3] if (len(challenge) > 2 and challenge[2] and len(challenge[2]) > 3) else None
                if not script_path:
                    raise ChallengeFetchError(f"Missing script path in WAA challenge: {resp.text[:200]}")

                script_url = "https:" + script_path if script_path.startswith("//") else script_path
                script_resp = await session.get(script_url)
                if script_resp.status_code != 200:
                    raise ChallengeFetchError(
                        f"Failed to download Botguard script from {script_url}: HTTP {script_resp.status_code}"
                    )

                script_code = script_resp.text
                return bytecode, script_code

        except ChallengeFetchError:
            raise
        except Exception as e:
            raise ChallengeFetchError(f"Failed to communicate with Google WAA: {e}") from e
