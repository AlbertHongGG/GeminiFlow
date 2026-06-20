from __future__ import annotations

import json
import random
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

from ..types import GeminiTokens


GEMINI_BASE_URL = "https://gemini.google.com"
REQUEST_URL = (
    "https://gemini.google.com/_/BardChatUi/data/assistant.lamda."
    "BardFrontendService/StreamGenerate"
)
REQUEST_BL_PARAM = "boq_assistant-bard-web-server_20260618.10_p0"

DEFAULT_HEADERS = {
    "authority": "gemini.google.com",
    "origin": "https://gemini.google.com",
    "referer": "https://gemini.google.com/",
    "x-same-domain": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

REQUIRED_COOKIE_NAME = "__Secure-1PSID"

MODEL_HEADERS: Dict[str, Dict[str, str]] = {
    "gemini-3-pro": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4,5,6,8],null,null,2,null,null,3,1,"{ext_uuid}"]'
    },
    "gemini-3.5-flash": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"56fdd199312815e2",null,null,0,[4,5,6,8],null,null,2,null,null,1,1,"{ext_uuid}"]'
    },
    "gemini-3-pro-image-preview": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4,5,6,8],null,null,2,null,null,3,2,"{ext_uuid}"]'
    },
}


@dataclass(frozen=True)
class GeminiRequest:
    prompt: str
    language: str
    tokens: GeminiTokens
    model: str
    uploads: Optional[Sequence[Tuple[str, str]]] = None
    conversation_ids: Optional[Sequence[str]] = None
    req_uuid: str = field(default_factory=lambda: str(uuid.uuid4()).upper())
    ext_uuid: str = field(default_factory=lambda: str(uuid.uuid4()).upper())

    def params(self) -> Dict[str, str]:
        return {
            "bl": REQUEST_BL_PARAM,
            "hl": self.language,
            "_reqid": str(random.randint(1111, 9999)),
            "rt": "c",
            "f.sid": "" if self.tokens.sid is None else self.tokens.sid,
        }

    def data(self) -> Dict[str, str]:
        base_headers = MODEL_HEADERS.get(self.model)
        p79, p80 = 1, 1
        if base_headers and "x-goog-ext-525001261-jspb" in base_headers:
            try:
                arr = json.loads(base_headers["x-goog-ext-525001261-jspb"])
                if len(arr) >= 16:
                    p79, p80 = arr[14], arr[15]
            except Exception:
                pass

        c_id, r_id, rc_id = "", "", ""
        if self.conversation_ids and len(self.conversation_ids) >= 2:
            c_id = self.conversation_ids[0]
            r_id = self.conversation_ids[1]
            if len(self.conversation_ids) >= 3:
                rc_id = self.conversation_ids[2]

        if "gemini-3-pro" in self.model or "gemini-3.5-flash" in self.model:
            inner = build_request(self.prompt, self.language, uploads=self.uploads, req_uuid=self.req_uuid, p79=p79, p80=p80, c_id=c_id, r_id=r_id, rc_id=rc_id)
        else:
            inner = build_request(self.prompt, self.language, uploads=self.uploads, c_id=c_id, r_id=r_id, rc_id=rc_id)
        return {
            "at": self.tokens.snlm0e,
            "f.req": json.dumps([None, json.dumps(inner)]),
        }

    def headers(self) -> Optional[Dict[str, str]]:
        base_headers = MODEL_HEADERS.get(self.model)
        if not base_headers:
            return None
        
        headers = dict(base_headers)
        if "x-goog-ext-525001261-jspb" in headers:
            headers["x-goog-ext-525001261-jspb"] = headers["x-goog-ext-525001261-jspb"].format(ext_uuid=self.ext_uuid)
        
        if "gemini-3-pro" in self.model or "gemini-3.5-flash" in self.model:
            headers["x-goog-ext-525005358-jspb"] = json.dumps([self.req_uuid, 1], separators=(",", ":"))
            
        return headers


def extract_tokens(html: str) -> Optional[GeminiTokens]:
    snlm0e_match = re.search(r'SNlM0e\\\":\\\"(.*?)\\\"', html)
    if not snlm0e_match:
        snlm0e_match = re.search(r'SNlM0e":"(.*?)"', html)
    snlm0e = snlm0e_match.group(1) if snlm0e_match else None

    sid_match = re.search(r'"FdrFJe":"([\d-]+)"', html)
    sid = sid_match.group(1) if sid_match else None

    if not snlm0e:
        return None
    return GeminiTokens(snlm0e=snlm0e, sid=sid)


def build_request(
    prompt: str,
    language: str,
    *,
    uploads: Optional[Sequence[Tuple[str, str]]] = None,
    req_uuid: Optional[str] = None,
    p79: int = 1,
    p80: int = 1,
    c_id: str = "",
    r_id: str = "",
    rc_id: str = "",
) -> list:
    image_list = (
        [[[upload_ref, 1], image_name] for upload_ref, image_name in uploads]
        if uploads
        else []
    )
    if req_uuid is None:
        return [
            [prompt, 0, None, image_list, None, None, 0],
            [language],
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
        arr[0] = [prompt, 0, None, image_list, None, None, 0]
        arr[1] = [language]
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
        arr[59] = req_uuid
        arr[61] = []
        arr[68] = 1
        arr[79] = p79
        arr[80] = p80
        return arr


def iter_response_text_chunks(full_text: str) -> Iterator[str]:
    last_content = ""
    for raw_line in full_text.split("\n"):
        delta, last_content, _ = extract_text_delta_from_raw_line(raw_line, last_content)
        if delta:
            yield delta


def extract_text_delta_from_raw_line(raw_line: str, last_content: str) -> Tuple[Optional[str], str, Optional[list]]:
    """Extract incremental text delta and conversation IDs from one StreamGenerate response line.

    Returns (delta, new_last_content, ids). When the line doesn't contain text, returns (None, last_content, ids).
    """

    def _flatten_strings(value):
        if isinstance(value, str):
            if value and not value.startswith("rc_"):
                yield value
            return
        if isinstance(value, list):
            for item in value:
                yield from _flatten_strings(item)

    def _extract_content(response_part):
        try:
            content = response_part[4][0][1][0]
            if isinstance(content, str):
                return content
        except Exception:
            pass

        try:
            content = response_part[4][0][1]
            if isinstance(content, str):
                return content
            if isinstance(content, list) and content and isinstance(content[0], str):
                return content[0]
        except Exception:
            pass

        try:
            candidates = list(_flatten_strings(response_part[4]))
            if candidates:
                return max(candidates, key=len)
        except Exception:
            pass

        return None

    try:
        line = json.loads(raw_line)
    except Exception:
        return None, last_content, None
    if not isinstance(line, list) or not line:
        return None, last_content, None

    try:
        if len(line[0]) < 3 or not line[0][2]:
            return None, last_content, None
        response_part = json.loads(line[0][2])
        if not response_part:
            return None, last_content, None
    except Exception:
        return None, last_content, None

    ids = None
    try:
        if len(response_part) > 1 and isinstance(response_part[1], list) and response_part[1]:
            if isinstance(response_part[1][0], str) and response_part[1][0].startswith("c_"):
                ids = response_part[1]
    except Exception:
        pass

    try:
        if len(response_part) < 5:
            return None, last_content, ids
        content = _extract_content(response_part)
        if not content:
            return None, last_content, ids
    except Exception:
        return None, last_content, ids

    if last_content and content.startswith(last_content):
        return content[len(last_content) :], content, ids
    return content, content, ids


def extract_image_candidates_from_raw_line(raw_line: str) -> Sequence[str]:
    """Extract image candidates (URLs or data URLs) from one StreamGenerate raw line."""

    def _walk_strings(value: Any) -> Iterator[str]:
        if isinstance(value, str):
            yield value
            return
        if isinstance(value, list):
            for item in value:
                yield from _walk_strings(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                yield from _walk_strings(item)

    def _is_likely_image_url(text: str) -> bool:
        if text.startswith("data:image/"):
            return True
        if not (text.startswith("https://") or text.startswith("http://")):
            return False
        lowered = text.lower()
        # Heuristics: Gemini web responses often reference these domains for media.
        if any(d in lowered for d in ["googleusercontent.com", "gstatic.com", "content-push.googleapis.com"]):
            return True
        if any(lowered.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            return True
        return False

    try:
        line = json.loads(raw_line)
    except Exception:
        return []
    if not isinstance(line, list) or not line:
        return []

    try:
        if len(line[0]) < 3 or not line[0][2]:
            return []
        response_part = json.loads(line[0][2])
    except Exception:
        return []

    out: list[str] = []
    seen: set[str] = set()
    for s in _walk_strings(response_part):
        if not s or s in seen:
            continue
        if _is_likely_image_url(s):
            seen.add(s)
            out.append(s)
    return out
