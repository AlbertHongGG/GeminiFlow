import logging
from typing import AsyncGenerator, Optional, List, Tuple
from gemini_flow.domain.interfaces import IChatProvider, IHttpClient, ITokenSigner
from gemini_flow.domain.entities import ChatRequest, ChatResponseChunk, SessionData, GeminiTokens, ImagePayload, BotguardToken
from gemini_flow.domain.exceptions import NetworkError, ProtocolError, AttestationError
from gemini_flow.config import UPLOAD_IMAGE_HEADERS, UPLOAD_IMAGE_URL, GEMINI_REQUEST_URL, REQUEST_BL_PARAM
from gemini_flow.infrastructure.attestation import EmbeddedV8TokenSigner
from .protocol import GeminiProtocolEngine
from .parser import StreamParser

logger = logging.getLogger("gemini_flow.api_client")

class GeminiAPIClient(IChatProvider):
    def __init__(
        self,
        http_client: IHttpClient,
        server_bl: str = REQUEST_BL_PARAM,
        token_signer: Optional[ITokenSigner] = None,
        proxy: Optional[str] = None,
    ):
        self.http_client = http_client
        self.protocol_engine = GeminiProtocolEngine(server_bl=server_bl)
        effective_proxy = proxy or getattr(http_client, "proxy", None)
        self.token_signer = token_signer if token_signer is not None else EmbeddedV8TokenSigner(proxy=effective_proxy)

    async def upload_images(self, images: List[ImagePayload]) -> List[Tuple[str, str]]:
        uploads = []
        for img in images:
            try:
                headers = {
                    **UPLOAD_IMAGE_HEADERS,
                    "size": str(len(img.data)),
                    "x-goog-upload-command": "start",
                }
                data_name = f"File name: {img.filename}" if img.filename else None
                resp = await self.http_client.post_form(UPLOAD_IMAGE_URL, data=data_name, headers=headers)
                upload_url = resp.headers.get("X-Goog-Upload-Url")
                if not upload_url:
                    raise NetworkError("Missing X-Goog-Upload-Url")
                
                headers["x-goog-upload-command"] = "upload, finalize"
                headers["X-Goog-Upload-Offset"] = "0"
                resp = await self.http_client.post_form(upload_url, data=img.data, headers=headers)
                upload_ref = await resp.text()
                uploads.append((upload_ref, img.filename))
            except Exception as e:
                logger.error(f"Image upload failed: {e}")
                raise NetworkError(f"Image upload failed: {e}") from e
        return uploads

    async def stream_generate(
        self, 
        request: ChatRequest, 
        tokens: GeminiTokens,
        session_data: Optional[SessionData] = None
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        
        # 1. Upload images if attached
        uploads = []
        if request.images:
            logger.info(f"Uploading {len(request.images)} images...")
            uploads = await self.upload_images(request.images)

        # 2. Cryptographic Botguard Attestation Signing (Content-Bound)
        botguard_token = None
        botguard_salt = None
        if self.token_signer:
            conv_id = session_data.conversation_id if session_data else None
            bg_token = await self.token_signer.sign(request.effective_prompt, conv_id)
            botguard_token = bg_token.token
            botguard_salt = bg_token.salt

        # 3. Protocol Request Construction
        proto_req = self.protocol_engine.build_request(
            request=request,
            tokens=tokens,
            session_data=session_data,
            uploads=uploads,
            botguard_token=botguard_token,
            botguard_salt=botguard_salt,
        )
        params = proto_req.params
        headers = proto_req.headers
        data = proto_req.data

        parser = StreamParser()
        emitted_session = False
        current_conv_id = session_data.conversation_id if session_data else None
        current_cont_token = session_data.continuation_token if session_data else None
        last_emitted_cont_token = None
        final_image_candidate = None
        fallback_image_candidate = None
        
        buffer = ""
        logger.debug("Generating stream...")
        
        stream_finished = False
        async for chunk in self.http_client.post_stream(GEMINI_REQUEST_URL, params=params, data=data, headers=headers):
            buffer += chunk
            while "\n" in buffer:
                raw_line, buffer = buffer.split("\n", 1)
                raw_line = raw_line.rstrip("\r")
                if not raw_line: continue
                
                for url in parser.extract_image_candidates(raw_line):
                    image_type = parser.classify_image_url(url)
                    if image_type == "placeholder":
                        if not fallback_image_candidate: fallback_image_candidate = url
                    elif image_type == "output":
                        final_image_candidate = url

                parsed_delta = parser.extract_text_delta(raw_line)
                
                if parsed_delta.conversation_id:
                    current_conv_id = parsed_delta.conversation_id
                if parsed_delta.continuation_token:
                    current_cont_token = parsed_delta.continuation_token

                if current_conv_id and not emitted_session:
                    emitted_session = True
                    yield ChatResponseChunk(
                        conversation_id=current_conv_id,
                        continuation_token=current_cont_token,
                    )
                    last_emitted_cont_token = current_cont_token

                if parsed_delta.text:
                    yield ChatResponseChunk(text=parsed_delta.text)

                if parser.is_end_of_stream(raw_line):
                    stream_finished = True
                    break
            
            if stream_finished:
                break

        # Flush buffer
        if buffer.strip():
            raw_line = buffer.rstrip("\r\n")
            for url in parser.extract_image_candidates(raw_line):
                image_type = parser.classify_image_url(url)
                if image_type == "placeholder":
                    if not fallback_image_candidate: fallback_image_candidate = url
                elif image_type == "output":
                    final_image_candidate = url
            
            parsed_delta = parser.extract_text_delta(raw_line)
            if parsed_delta.conversation_id:
                current_conv_id = parsed_delta.conversation_id
            if parsed_delta.continuation_token:
                current_cont_token = parsed_delta.continuation_token

            if current_conv_id and not emitted_session:
                emitted_session = True
                yield ChatResponseChunk(
                    conversation_id=current_conv_id,
                    continuation_token=current_cont_token,
                )
                last_emitted_cont_token = current_cont_token

            if parsed_delta.text:
                yield ChatResponseChunk(text=parsed_delta.text)

        # Emit final session update if continuation token arrived late
        if current_conv_id and current_cont_token != last_emitted_cont_token:
            yield ChatResponseChunk(
                conversation_id=current_conv_id,
                continuation_token=current_cont_token,
            )

        # Return final image
        img_url = final_image_candidate or fallback_image_candidate
        if img_url:
            logger.info(f"Image generation detected: {img_url}")
            yield ChatResponseChunk(image_url=img_url)
