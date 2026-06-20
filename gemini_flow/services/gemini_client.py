import asyncio
import base64
import os
import re
import time
from pathlib import Path
from typing import Optional, AsyncGenerator, List, Tuple
from ..models import ChatRequest, ChatResponseChunk, ImagePayload, SessionData
from ..config import DEFAULT_COOKIES_DIR, GEMINI_BASE_URL, GEMINI_REQUEST_URL, UPLOAD_IMAGE_URL, UPLOAD_IMAGE_HEADERS, REQUEST_BL_PARAM, DEFAULT_HTTP_HEADERS, MODEL_HEADERS, DEFAULT_IMAGE_OUTPUT_DIR
from ..exceptions import NetworkError, PayloadError, AuthenticationError
from ..infra.cookie_manager import CookieManager
from ..infra.auth import AuthManager
from ..infra.http_client import HttpClient
from ..core.protocol_builder import extract_tokens, ProtocolBuilder
from ..core.response_parser import ResponseParser

class GeminiClient:
    def __init__(self, cookies_dir: Path = DEFAULT_COOKIES_DIR):
        self.cookies_dir = cookies_dir
        self.cookie_manager = CookieManager(cookies_dir)
        self.auth_manager = AuthManager(cookies_dir)

    async def _upload_images(self, images: List[ImagePayload], proxy: Optional[str]) -> List[Tuple[str, str]]:
        client = HttpClient(headers=UPLOAD_IMAGE_HEADERS, proxy=proxy)
        uploads = []
        for img in images:
            try:
                headers = {
                    "size": str(len(img.data)),
                    "x-goog-upload-command": "start",
                }
                data_name = f"File name: {img.filename}" if img.filename else None
                resp = await client.post_form(UPLOAD_IMAGE_URL, data=data_name, headers=headers)
                upload_url = resp.headers.get("X-Goog-Upload-Url")
                if not upload_url:
                    raise NetworkError("Missing X-Goog-Upload-Url")
                
                headers["x-goog-upload-command"] = "upload, finalize"
                headers["X-Goog-Upload-Offset"] = "0"
                resp = await client.post_form(upload_url, data=img.data, headers=headers)
                upload_ref = await resp.text()
                uploads.append((upload_ref, img.filename))
            except Exception as e:
                raise NetworkError(f"Image upload failed: {e}") from e
        return uploads

    async def stream_chat(self, request: ChatRequest) -> AsyncGenerator[ChatResponseChunk, None]:
        try:
            cookies = self.cookie_manager.get_google_cookies()
        except AuthenticationError:
            if not request.auto_refresh_cookies:
                raise
            await self.auth_manager.ensure_cookies()
            cookies = self.cookie_manager.get_google_cookies()

        client = HttpClient(headers=DEFAULT_HTTP_HEADERS, cookies=cookies, proxy=request.proxy)

        # Get tokens
        try:
            html = await client.get_text(GEMINI_BASE_URL)
            tokens = extract_tokens(html)
            if not tokens:
                raise AuthenticationError("Tokens not found, cookies might be expired.")
        except Exception:
            if not request.auto_refresh_cookies:
                raise
            await self.auth_manager.ensure_cookies()
            cookies = self.cookie_manager.get_google_cookies()
            client.cookies = cookies
            html = await client.get_text(GEMINI_BASE_URL)
            tokens = extract_tokens(html)
            if not tokens:
                raise AuthenticationError("Tokens not found even after refresh.")

        uploads = []
        if request.images:
            uploads = await self._upload_images(request.images, request.proxy)

        from ..services.session_manager import SessionManager
        session_manager = SessionManager()
        conversation_ids = []
        if request.session_id:
            sess = session_manager.load(request.session_id)
            if sess:
                conversation_ids = sess.conversation_ids

        builder = ProtocolBuilder(
            prompt=request.prompt,
            language=request.language,
            model=request.model,
            tokens=tokens,
            uploads=uploads,
            conversation_ids=conversation_ids
        )

        params = builder.build_params(REQUEST_BL_PARAM)
        data = builder.build_payload(MODEL_HEADERS)
        headers = builder.build_headers(MODEL_HEADERS)

        parser = ResponseParser()
        emitted_session_ids = False
        
        normalized_model = request.model.strip().lower()
        is_image_model = "-image" in normalized_model
        
        final_image_candidate = None
        fallback_image_candidate = None
        
        # Helper to normalize URL
        _CONTROL_RE = re.compile(r"[\x00-\x1F\x7F\u200B\u200C\u200D\uFEFF]")
        def _normalize(v): return _CONTROL_RE.sub("", v.strip())
        
        def _is_placeholder(url):
            return "googleusercontent.com/image_generation_content/" in url or ("lh3.googleusercontent.com/gg/" in url and "lh3.googleusercontent.com/gg-dl/" not in url)
            
        def _is_output(url):
            return url.startswith("data:image/") or "lh3.googleusercontent.com/gg-dl/" in url
            
        async for chunk in client.post_stream(GEMINI_REQUEST_URL, params=params, data=data, headers=headers):
            raw_line = chunk.rstrip("\r\n")
            if not raw_line: continue
            
            if is_image_model:
                for candidate in parser.extract_image_candidates(raw_line):
                    norm = _normalize(candidate)
                    if not norm: continue
                    if _is_placeholder(norm):
                        if fallback_image_candidate is None: fallback_image_candidate = norm
                        continue
                    if _is_output(norm):
                        final_image_candidate = norm

            delta, ids = parser.extract_text_delta(raw_line)
            
            if ids and not emitted_session_ids:
                emitted_session_ids = True
                yield ChatResponseChunk(session_ids=ids)
                if request.session_id:
                    session_manager.save(SessionData(session_id=request.session_id, conversation_ids=ids))

            if delta:
                yield ChatResponseChunk(text=delta)

        if is_image_model:
            img_url = final_image_candidate or fallback_image_candidate
            if img_url:
                chunk = ChatResponseChunk(image_url=img_url)
                if request.save_images and final_image_candidate:
                    try:
                        out_dir = DEFAULT_IMAGE_OUTPUT_DIR
                        out_dir.mkdir(parents=True, exist_ok=True)
                        out_path = out_dir / f"gemini_{request.model}_{int(time.time())}.png"
                        if img_url.startswith("data:image/"):
                            _, b64 = img_url.split(",", 1)
                            out_path.write_bytes(base64.b64decode(b64))
                            chunk.image_saved_path = str(out_path)
                        else:
                            img_data = await client.download_file(img_url)
                            out_path.write_bytes(img_data)
                            chunk.image_saved_path = str(out_path)
                    except Exception as e:
                        if request.debug:
                            print(f"[debug] Save image failed: {e}")
                yield chunk
