import json
import random
import uuid
import re
from typing import Dict, List, Optional, Tuple, Sequence
from ..models import GeminiTokens

def extract_tokens(html: str) -> Optional[GeminiTokens]:
    """Extract SNlM0e and sid tokens from Google's HTML response."""
    snlm0e_match = re.search(r'SNlM0e\\\":\\\"(.*?)\\\"', html)
    if not snlm0e_match:
        snlm0e_match = re.search(r'SNlM0e":"(.*?)"', html)
    snlm0e = snlm0e_match.group(1) if snlm0e_match else None

    sid_match = re.search(r'"FdrFJe":"([\d-]+)"', html)
    sid = sid_match.group(1) if sid_match else None

    if not snlm0e:
        return None
    return GeminiTokens(snlm0e=snlm0e, sid=sid)

class ProtocolBuilder:
    def __init__(self, prompt: str, language: str, model: str, tokens: GeminiTokens, uploads: Optional[Sequence[Tuple[str, str]]] = None, conversation_ids: Optional[Sequence[str]] = None):
        self.prompt = prompt
        self.language = language
        self.model = model
        self.tokens = tokens
        self.uploads = uploads or []
        self.conversation_ids = conversation_ids or []
        self.req_uuid = str(uuid.uuid4()).upper()
        self.ext_uuid = str(uuid.uuid4()).upper()

    def build_params(self, bl_param: str) -> Dict[str, str]:
        """Build URL parameters for StreamGenerate request."""
        return {
            "bl": bl_param,
            "hl": self.language,
            "_reqid": str(random.randint(1111, 9999)),
            "rt": "c",
            "f.sid": "" if self.tokens.sid is None else self.tokens.sid,
        }

    def build_payload(self, model_headers: Dict[str, Dict[str, str]]) -> Dict[str, str]:
        """Build form-data payload for StreamGenerate request."""
        base_headers = model_headers.get(self.model)
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

        is_pro = "gemini-3-pro" in self.model or "gemini-3.5-flash" in self.model
        
        inner = self._build_inner_request(
            c_id=c_id, 
            r_id=r_id, 
            rc_id=rc_id, 
            p79=p79 if is_pro else 1, 
            p80=p80 if is_pro else 1,
            use_uuid=is_pro
        )

        return {
            "at": self.tokens.snlm0e,
            "f.req": json.dumps([None, json.dumps(inner)]),
        }

    def build_headers(self, base_model_headers: Dict[str, Dict[str, str]]) -> Optional[Dict[str, str]]:
        """Build specific headers for the model."""
        base_headers = base_model_headers.get(self.model)
        if not base_headers:
            return None
        
        headers = dict(base_headers)
        if "x-goog-ext-525001261-jspb" in headers:
            headers["x-goog-ext-525001261-jspb"] = headers["x-goog-ext-525001261-jspb"].format(ext_uuid=self.ext_uuid)
        
        if "gemini-3-pro" in self.model or "gemini-3.5-flash" in self.model:
            headers["x-goog-ext-525005358-jspb"] = json.dumps([self.req_uuid, 1], separators=(",", ":"))
            
        return headers

    def _build_inner_request(self, c_id: str, r_id: str, rc_id: str, p79: int, p80: int, use_uuid: bool) -> List:
        """Construct the inner JSON array required by Gemini."""
        image_list = [
            [[upload_ref, 1], image_name] for upload_ref, image_name in self.uploads
        ]

        if not use_uuid:
            return [
                [self.prompt, 0, None, image_list, None, None, 0],
                [self.language],
                [c_id, r_id, rc_id, None, None, None, None, None, None, ""],
                None,
                None,
                None,
                [1],
                0,
                [],
                [],
                1,
                0,
            ]
        else:
            arr = [None] * 81
            arr[0] = [self.prompt, 0, None, image_list, None, None, 0]
            arr[1] = [self.language]
            arr[2] = [c_id, r_id, rc_id, None, None, None, None, None, None, ""]
            arr[6] = [0]
            arr[7] = 1
            arr[10] = 1
            arr[11] = 0
            arr[17] = [[0]]
            arr[18] = 0
            arr[27] = 1
            arr[30] = [4]
            arr[41] = [1]
            arr[53] = 0
            arr[59] = self.req_uuid
            arr[61] = []
            arr[68] = 1
            arr[79] = p79
            arr[80] = p80
            return arr
