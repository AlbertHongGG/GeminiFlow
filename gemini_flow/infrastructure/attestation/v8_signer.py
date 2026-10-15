import hashlib
import logging
import os
import time
from typing import Optional
from ...domain.entities import BotguardToken
from ...domain.interfaces import ITokenSigner
from ...domain.exceptions import VmExecutionError
from .waa_client import WaaClient
from .v8_runtime import BotguardV8Runtime

logger = logging.getLogger(__name__)

class EmbeddedV8TokenSigner(ITokenSigner):
    """
    Implementation of ITokenSigner using Google's embedded V8 engine via py_mini_racer.
    Runs completely in-process with zero browser, zero GUI, and zero WebView dependencies.
    """

    def __init__(
        self,
        waa_client: Optional[WaaClient] = None,
        proxy: Optional[str] = None,
    ):
        self._waa_client = waa_client or WaaClient(proxy=proxy)
        self._current_runtime: Optional[BotguardV8Runtime] = None
        self._current_bytecode: Optional[str] = None

    async def sign(
        self, prompt: str, conversation_id: Optional[str] = None
    ) -> BotguardToken:
        """
        Signs the prompt and conversation ID, producing a Content-Bound Botguard token and random salt.
        """
        t0 = time.time()
        
        # 1. Generate 16 bytes cryptographic random salt (inner[4])
        salt_bytes = os.urandom(16)
        salt_hex = salt_bytes.hex()

        # 2. Compute Content-Bound Query Hash (qh)
        # qh = SHA256(prompt + salt_hex)
        to_hash = (prompt + salt_hex).encode("utf-8")
        query_hash = hashlib.sha256(to_hash).hexdigest()

        # 3. Retrieve challenge and script from WAA
        bytecode, script_code = await self._waa_client.get_challenge()

        # 4. Check if runtime needs to be re-initialized (e.g. challenge rotated)
        if self._current_runtime is None or self._current_bytecode != bytecode:
            if self._current_runtime is not None:
                self._current_runtime.close()
            self._current_runtime = BotguardV8Runtime(script_code, bytecode)
            self._current_bytecode = bytecode

        # 5. Execute snapshot in V8 engine with automatic recovery
        cid_str = conversation_id or ""
        try:
            token_str = self._current_runtime.generate_token(query_hash, cid_str)
        except VmExecutionError as ex:
            logger.warning(
                "Initial Botguard execution encountered '%s'. Re-initializing with fresh challenge...",
                ex,
            )
            bytecode, script_code = await self._waa_client._fetch_fresh_challenge()
            if self._current_runtime is not None:
                self._current_runtime.close()
            self._current_runtime = BotguardV8Runtime(script_code, bytecode)
            self._current_bytecode = bytecode
            token_str = self._current_runtime.generate_token(query_hash, cid_str)

        elapsed_ms = (time.time() - t0) * 1000.0
        logger.debug(
            "Botguard token generated via embedded V8 in %.1fms (token len=%d)",
            elapsed_ms,
            len(token_str)
        )

        return BotguardToken(
            token=token_str,
            salt=salt_hex,
            created_at=time.time()
        )

    def close(self) -> None:
        """
        Explicitly disposes the current V8 runtime instance.
        """
        if self._current_runtime is not None:
            self._current_runtime.close()
            self._current_runtime = None
            self._current_bytecode = None
