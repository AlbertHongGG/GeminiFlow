import abc
import json
import uuid
import random
from typing import Dict, List, Optional, Tuple, Sequence
from gemini_flow.domain.entities import GeminiTokens, ChatRequest

class BasePayloadBuilder(abc.ABC):
    def __init__(self, request: ChatRequest, tokens: GeminiTokens, uploads: Optional[Sequence[Tuple[str, str]]] = None, conversation_ids: Optional[Sequence[str]] = None):
        self.request = request
        self.tokens = tokens
        self.uploads = uploads or []
        self.conversation_ids = conversation_ids or []
        self.req_uuid = str(uuid.uuid4()).upper()
        self.ext_uuid = str(uuid.uuid4()).upper()
        
        self.prompt = request.prompt
        if request.system_prompt:
            self.prompt = f"System:\n{request.system_prompt}\n\nUser:\n{request.prompt}"

    def build_params(self, bl_param: str) -> Dict[str, str]:
        return {
            "bl": bl_param,
            "hl": self.request.language,
            "_reqid": str(random.randint(1111, 9999)),
            "rt": "c",
            "f.sid": "" if self.tokens.sid is None else self.tokens.sid,
        }

    def build_payload(self, model_headers: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        base_headers = model_headers.get(self.request.model)
        p79, p80 = 1, 1
        if base_headers and "x-goog-ext-525001261-jspb" in base_headers:
            try:
                arr = json.loads(base_headers["x-goog-ext-525001261-jspb"])
                if len(arr) >= 16:
                    p79, p80 = arr[14], arr[15]
            except Exception:
                pass

        c_id, r_id, rc_id = "", "", ""
        if len(self.conversation_ids) >= 2:
            c_id = self.conversation_ids[0]
            r_id = self.conversation_ids[1]
            if len(self.conversation_ids) >= 3:
                rc_id = self.conversation_ids[2]

        inner = self._build_inner_request(c_id, r_id, rc_id, p79, p80)

        return {
            "at": self.tokens.snlm0e,
            "f.req": json.dumps([None, json.dumps(inner)]),
        }

    def build_headers(self, base_model_headers: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
        base_headers = base_model_headers.get(self.request.model)
        if not base_headers:
            return None
        
        headers = dict(base_headers)
        if "x-goog-ext-525001261-jspb" in headers:
            headers["x-goog-ext-525001261-jspb"] = headers["x-goog-ext-525001261-jspb"].format(ext_uuid=self.ext_uuid)
        
        return self._enrich_headers(headers)

    @abc.abstractmethod
    def _build_inner_request(self, c_id: str, r_id: str, rc_id: str, p79: int, p80: int) -> List:
        """Constructs the JSON array payload specific to the model family."""
        pass
        
    def _enrich_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Allows specific builders to add extra headers."""
        return headers
