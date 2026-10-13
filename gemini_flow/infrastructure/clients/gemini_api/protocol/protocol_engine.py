from __future__ import annotations
import uuid
import random
from typing import Dict, Sequence, Tuple, Optional
from dataclasses import dataclass

from gemini_flow.domain.entities import ChatRequest, GeminiTokens, SessionData
from .header_builder import JspbHeaderBuilder
from .payload_builder import GeminiPayloadBuilder

@dataclass
class ProtocolRequest:
    params: Dict[str, str]
    headers: Dict[str, str]
    data: Dict[str, str]

class GeminiProtocolEngine:
    """
    High-level engine that orchestrates the generation of request query parameters,
    JSPB headers, and the form-encoded payload for Gemini StreamGenerate requests.
    """

    def __init__(self, server_bl: str):
        self.server_bl = server_bl
        self.session_uuid = str(uuid.uuid4()).upper()

    def build_request(
        self,
        request: ChatRequest,
        tokens: GeminiTokens,
        session_data: Optional[SessionData] = None,
        uploads: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> ProtocolRequest:
        req_uuid = str(uuid.uuid4()).upper()
        model_spec = request.model_spec

        # 1. URL Query Parameters
        params = {
            "bl": self.server_bl,
            "hl": request.language,
            "_reqid": str(random.randint(111111, 9999999)),
            "rt": "c",
            "f.sid": tokens.sid or "",
        }

        # 2. JSPB Extension Headers
        header_builder = JspbHeaderBuilder(
            model_spec=model_spec,
            session_uuid=self.session_uuid,
            req_uuid=req_uuid,
            server_bl=self.server_bl,
        )
        headers = header_builder.build_all_headers()

        # 3. Payload
        turn_index = session_data.turn_index if session_data else 0
        conversation_id = session_data.conversation_id if session_data else None
        continuation_token = session_data.continuation_token if session_data else None

        payload_builder = GeminiPayloadBuilder(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            language=request.language,
            model_spec=model_spec,
            req_uuid=req_uuid,
            uploads=uploads,
            conversation_id=conversation_id,
            continuation_token=continuation_token,
            turn_index=turn_index,
        )
        data = payload_builder.build_post_data(at_token=tokens.snlm0e)

        return ProtocolRequest(params=params, headers=headers, data=data)
