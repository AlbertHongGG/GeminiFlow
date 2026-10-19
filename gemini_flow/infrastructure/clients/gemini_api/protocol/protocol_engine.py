from __future__ import annotations
import uuid
import random
import string
from typing import Dict, Optional, Sequence
from dataclasses import dataclass

from gemini_flow.domain.entities import ChatRequest, GeminiCredentials, SessionData, UploadedImageAttachment
from gemini_flow.infrastructure.auth.sapisid_signer import SAPISIDSigner
from .header_builder import WebChannelHeaderBuilder
from .payload_builder import WebChannelPayloadBuilder

@dataclass
class WebChannelRequestPlan:
    session_uuid: str
    req_uuid: str
    base_rid: int
    handshake_params: Dict[str, str]
    handshake_data: Dict[str, str]
    payload_builder: WebChannelPayloadBuilder
    header_builder: WebChannelHeaderBuilder

def generate_random_zx(length: int = 12) -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))

class WebChannelProtocolEngine:
    """
    Orchestrates the creation of WebChannel handshake, stream query parameters,
    and binary Protobuf payloads for Google Gemini.
    """

    def __init__(self, default_server_bl: str = "boq_gemini-web-uiserver_20261016.00_p0"):
        self.default_server_bl = default_server_bl
        self.session_uuid = str(uuid.uuid4()).upper()

    def plan_turn(
        self,
        request: ChatRequest,
        credentials: GeminiCredentials,
        session_data: Optional[SessionData] = None,
        botguard_token: Optional[str] = None,
        botguard_salt: Optional[str] = None,
        uploaded_images: Sequence[UploadedImageAttachment] = (),
    ) -> WebChannelRequestPlan:
        req_uuid = str(uuid.uuid4()).upper()
        base_rid = random.randint(10000, 89000)
        effective_bl = credentials.server_bl or self.default_server_bl

        # 1. Header Builder
        header_builder = WebChannelHeaderBuilder(
            model_spec=request.model_spec,
            session_uuid=self.session_uuid,
            req_uuid=req_uuid,
            server_bl=effective_bl,
        )

        auth_header = SAPISIDSigner.get_authorization_header(credentials.cookies)
        tunnel_headers = header_builder.build_tunnel_http_headers(
            authorization=auth_header,
            api_key=credentials.api_key,
        )

        # 2. Handshake Query Params
        handshake_params = {
            "VER": "8",
            "RID": str(base_rid),
            "CVER": "22",
            "X-HTTP-Session-Id": "gsessionid",
            "$httpHeaders": tunnel_headers,
            "zx": generate_random_zx(),
            "t": "1",
        }
        handshake_data = {"count": "0"}

        # 3. Payload Builder
        turn_index = session_data.turn_index if session_data else 0
        conversation_id = session_data.conversation_id if session_data else None
        continuation_token = session_data.continuation_token if session_data else None

        payload_builder = WebChannelPayloadBuilder(
            prompt=request.effective_prompt,
            language=request.language,
            model_spec=request.model_spec,
            req_uuid=req_uuid,
            conversation_id=conversation_id,
            continuation_token=continuation_token,
            turn_index=turn_index,
            botguard_token=botguard_token,
            botguard_salt=botguard_salt,
            uploaded_images=uploaded_images,
        )

        return WebChannelRequestPlan(
            session_uuid=self.session_uuid,
            req_uuid=req_uuid,
            base_rid=base_rid,
            handshake_params=handshake_params,
            handshake_data=handshake_data,
            payload_builder=payload_builder,
            header_builder=header_builder,
        )

    @staticmethod
    def build_stream_params(gsessionid: str, sid: str, aid: int = 0) -> Dict[str, str]:
        return {
            "gsessionid": gsessionid,
            "VER": "8",
            "RID": "rpc",
            "SID": sid,
            "AID": str(aid),
            "CI": "0",
            "TYPE": "xmlhttp",
            "zx": generate_random_zx(),
            "t": "1",
        }

    @staticmethod
    def build_upstream_params(gsessionid: str, sid: str, rid: int, aid: int = 0) -> Dict[str, str]:
        return {
            "VER": "8",
            "gsessionid": gsessionid,
            "SID": sid,
            "RID": str(rid),
            "AID": str(aid),
            "zx": generate_random_zx(),
            "t": "1",
        }
