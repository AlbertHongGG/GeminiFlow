from __future__ import annotations
import logging
import asyncio
from typing import AsyncGenerator, Optional, List, Tuple, Any
from gemini_flow.domain.interfaces import IChatProvider, IHttpClient, ITokenSigner, IImageUploader
from gemini_flow.domain.entities import (
    ChatRequest,
    ChatResponseChunk,
    SessionData,
    GeminiCredentials,
    ImagePayload,
)
from gemini_flow.config import GEMINI_PROCESS_SESSION_URL, REQUEST_BL_PARAM
from gemini_flow.infrastructure.attestation import EmbeddedV8TokenSigner
from gemini_flow.infrastructure.clients.gemini_uploader import GeminiImageUploader
from .protocol import WebChannelProtocolEngine
from .webchannel_parser import WebChannelStreamParser

import json
import re

logger = logging.getLogger("gemini_flow.webchannel_client")

class WebChannelChatProvider(IChatProvider):
    """
    Implements IChatProvider over Google's real-time WebChannel duplex protocol
    (geminiweb-pa.clients6.google.com/v1/processSession).
    """

    def __init__(
        self,
        http_client: IHttpClient,
        server_bl: str = REQUEST_BL_PARAM,
        token_signer: Optional[ITokenSigner] = None,
        image_uploader: Optional[IImageUploader] = None,
        proxy: Optional[str] = None,
    ):
        self.http_client = http_client
        self.protocol_engine = WebChannelProtocolEngine(default_server_bl=server_bl)
        effective_proxy = proxy or getattr(http_client, "proxy", None)
        self.token_signer = token_signer if token_signer is not None else EmbeddedV8TokenSigner(proxy=effective_proxy)
        self.image_uploader = image_uploader if image_uploader is not None else GeminiImageUploader(http_client)

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        return await self.image_uploader.upload_images(images)

    async def _send_upstream_payloads(
        self,
        plan: Any,
        gsessionid: str,
        sid: str,
        ready_evt: asyncio.Event,
    ) -> None:
        """Sends ofs=0 and ofs=1 with proper pacing once downstream stream is active."""
        await ready_evt.wait()

        # 1. ofs=0 (Metadata)
        params_0 = self.protocol_engine.build_upstream_params(gsessionid, sid, rid=plan.base_rid + 1, aid=0)
        data_0 = {
            "count": "1",
            "ofs": "0",
            "req0___data__": plan.payload_builder.build_metadata_payload(),
        }
        await self.http_client.post(GEMINI_PROCESS_SESSION_URL, params=params_0, data=data_0)

        # Brief pacing delay before prompt
        await asyncio.sleep(0.5)

        # 2. ofs=1 (Prompt)
        params_1 = self.protocol_engine.build_upstream_params(gsessionid, sid, rid=plan.base_rid + 2, aid=2)
        data_1 = {
            "count": "1",
            "ofs": "1",
            "req0___data__": plan.payload_builder.build_prompt_payload(),
        }
        await self.http_client.post(GEMINI_PROCESS_SESSION_URL, params=params_1, data=data_1)

    async def stream_generate(
        self,
        request: ChatRequest,
        tokens: Any,
        session_data: Optional[SessionData] = None,
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        # Normalize credentials
        if isinstance(tokens, GeminiCredentials):
            credentials = tokens
        elif hasattr(tokens, "cookies"):
            credentials = GeminiCredentials(
                cookies=tokens.cookies,
                server_bl=getattr(tokens, "server_bl", None),
                sid=getattr(tokens, "sid", None),
            )
        elif isinstance(tokens, dict):
            credentials = GeminiCredentials(cookies=tokens)
        else:
            credentials = GeminiCredentials(
                server_bl=getattr(tokens, "server_bl", None),
                sid=getattr(tokens, "sid", None),
            )

        # 1. Upload images if attached
        if request.images:
            await self.image_uploader.upload_images(request.images)

        # 2. Cryptographic Botguard Attestation
        botguard_token = None
        botguard_salt = None
        if self.token_signer:
            try:
                conv_id = session_data.conversation_id if session_data else None
                bg_token = await self.token_signer.sign(request.effective_prompt, conv_id)
                botguard_token = bg_token.token
                botguard_salt = bg_token.salt
            except Exception as e:
                logger.debug(f"Botguard attestation signing skipped: {e}")

        # 3. Plan Turn
        plan = self.protocol_engine.plan_turn(
            request=request,
            credentials=credentials,
            session_data=session_data,
            botguard_token=botguard_token,
            botguard_salt=botguard_salt,
        )

        # 4. Step 1: Handshake POST count=0
        logger.debug(f"Initiating WebChannel handshake RID={plan.base_rid}...")
        handshake_resp = await self.http_client.post(
            GEMINI_PROCESS_SESSION_URL,
            params=plan.handshake_params,
            data=plan.handshake_data,
        )
        gsessionid = handshake_resp.headers.get("x-http-session-id") or plan.session_uuid
        
        # Parse SID from handshake response body: [[0, ["c", "<SID>", ...]]]
        body = handshake_resp.content.decode("utf-8", errors="ignore").strip()
        clean_body = re.sub(r"^\d+\s*\n", "", body).strip()
        sid = None
        if clean_body.startswith("["):
            try:
                h_json = json.loads(clean_body, strict=False)
                if isinstance(h_json, list) and len(h_json) > 0 and len(h_json[0]) > 1:
                    sid = h_json[0][1][1]
            except Exception as e:
                logger.debug(f"Failed to parse SID from handshake body: {e}")
        
        if not sid:
            sid = credentials.sid or "sid_default"

        # 5. Launch upstream pushes when stream is active
        ready_evt = asyncio.Event()
        push_task = asyncio.create_task(self._send_upstream_payloads(plan, gsessionid, sid, ready_evt))

        # 6. Stream Downstream Responses
        stream_params = self.protocol_engine.build_stream_params(gsessionid=gsessionid, sid=sid)
        parser = WebChannelStreamParser()
        emitted_session = False
        current_conv_id = session_data.conversation_id if session_data else None
        current_cont_token = session_data.continuation_token if session_data else None
        last_emitted_cont_token = None
        received_chunks = 0

        logger.debug("Listening to downstream WebChannel stream...")
        try:
            stream_gen = self.http_client.get_stream(GEMINI_PROCESS_SESSION_URL, params=stream_params)
            ready_evt.set()

            async for chunk in stream_gen:
                if not chunk or not chunk.strip():
                    continue

                received_chunks += 1

                # Check for generated image URLs
                for img_url in parser.extract_image_candidates(chunk):
                    yield ChatResponseChunk(image_url=img_url)

                delta = parser.parse_frame(chunk)
                if delta.conversation_id:
                    current_conv_id = delta.conversation_id
                if delta.continuation_token:
                    current_cont_token = delta.continuation_token

                if current_conv_id and not emitted_session:
                    emitted_session = True
                    yield ChatResponseChunk(
                        conversation_id=current_conv_id,
                        continuation_token=current_cont_token,
                    )
                    last_emitted_cont_token = current_cont_token

                if delta.text:
                    yield ChatResponseChunk(
                        text=delta.text,
                        conversation_id=current_conv_id,
                        continuation_token=current_cont_token,
                    )

                if delta.continuation_token or parser.is_end_of_stream(chunk):
                    if current_cont_token and current_cont_token != last_emitted_cont_token:
                        yield ChatResponseChunk(
                            conversation_id=current_conv_id,
                            continuation_token=current_cont_token,
                        )
                        last_emitted_cont_token = current_cont_token
                    break
        finally:
            if not push_task.done():
                push_task.cancel()
            else:
                exc = push_task.exception()
                if exc:
                    logger.error(f"Upstream push task error: {exc}")

        # 7. Send ofs=2 (Ack)
        try:
            params_2 = self.protocol_engine.build_upstream_params(gsessionid, sid, rid=plan.base_rid + 3, aid=received_chunks)
            data_2 = {
                "count": "1",
                "ofs": "2",
                "req0___data__": plan.payload_builder.build_ack_payload(),
            }
            await self.http_client.post(GEMINI_PROCESS_SESSION_URL, params=params_2, data=data_2)
        except Exception as e:
            logger.debug(f"WebChannel ACK (ofs=2) skipped or non-fatal: {e}")

        # Final session update if continuation token updated
        if current_conv_id and current_cont_token != last_emitted_cont_token:
            yield ChatResponseChunk(
                conversation_id=current_conv_id,
                continuation_token=current_cont_token,
            )
