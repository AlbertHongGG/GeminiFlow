from __future__ import annotations
import json
import re
import base64
from typing import Any, Iterator, Optional, Tuple, List, NamedTuple, Union
from gemini_flow.infrastructure.protocol.protobuf import ProtobufReader, ProtoField
from gemini_flow.domain.exceptions import AuthenticationError, RateLimitError, GeminiFlowError

class ParsedStreamDelta(NamedTuple):
    text: Optional[str] = None
    conversation_id: Optional[str] = None
    continuation_token: Optional[str] = None

class WebChannelStreamParser:
    """
    Parses Google WebChannel downstream streaming frames from GET /v1/processSession?RID=rpc.
    Extracts incremental response tokens, conversation state, and multimodal assets.
    """

    CONV_ID_PATTERN = re.compile(r"^(c_[a-f0-9]{16})$")
    CONT_TOKEN_PATTERN = re.compile(r"^(Aw[A-Za-z0-9_-]{20,})$")
    IMAGE_URL_PATTERN = re.compile(
        r"https://(?:lh\d+\.googleusercontent\.com/(?:gg-dl/|ci/)[a-zA-Z0-9_\-=]+|drive\.google\.com/thumbnail\?[a-zA-Z0-9_=&-]+)"
    )

    def __init__(self) -> None:
        self.last_content: str = ""

    def check_control_error(self, raw_chunk: str) -> None:
        """
        Inspects WebChannel control frames for RPC error status codes.
        Raises AuthenticationError, RateLimitError, or GeminiFlowError immediately.
        """
        cleaned = self._strip_framing(raw_chunk)
        if not cleaned or not cleaned.startswith("["):
            return
        try:
            data = json.loads(cleaned, strict=False)

            def find_errors(node: Any) -> None:
                if isinstance(node, dict):
                    if "error" in node and isinstance(node["error"], dict):
                        err = node["error"]
                        code = err.get("code")
                        msg = err.get("message") or str(err)
                        if code == 401 or "UNAUTHENTICATED" in str(msg) or code == "401":
                            raise AuthenticationError(f"WebChannel RPC error 401: {msg}")
                        if code == 429 or "RESOURCE_EXHAUSTED" in str(msg) or code == "429":
                            raise RateLimitError(f"WebChannel RPC error 429: {msg}")
                        raise GeminiFlowError(f"WebChannel RPC error {code}: {msg}")
                    for v in node.values():
                        find_errors(v)
                elif isinstance(node, list):
                    for item in node:
                        find_errors(item)

            find_errors(data)
        except (AuthenticationError, RateLimitError, GeminiFlowError):
            raise
        except Exception:
            pass

    def extract_text_delta(self, raw_chunk: str) -> ParsedStreamDelta:
        return self.parse_frame(raw_chunk)

    def _strip_framing(self, raw_chunk: str) -> str:
        """Strips WebChannel chunk length prefixes (e.g., '142\\n') and leading delimiters."""
        s = raw_chunk.strip()
        if s.isdigit():
            return ""
        # If line starts with a number followed by newline or space, strip it
        match = re.match(r"^\d+\s*\n(.*)$", s, re.DOTALL)
        if match:
            s = match.group(1).strip()
        if s.startswith(")]}'"):
            s = s[4:].strip()
        return s

    def _find_strings(self, data: Any) -> Iterator[str]:
        if isinstance(data, str):
            if (data.startswith("[") and data.endswith("]")) or (data.startswith("{") and data.endswith("}")):
                try:
                    nested = json.loads(data, strict=False)
                    yield from self._find_strings(nested)
                    return
                except Exception:
                    pass
            yield data
        elif isinstance(data, list):
            for item in data:
                yield from self._find_strings(item)
        elif isinstance(data, dict):
            for val in data.values():
                yield from self._find_strings(val)

    def classify_image_url(self, url: str) -> str:
        if "drive.google.com" in url or "gg-dl" in url or "=s0-d" in url:
            return "output"
        return "placeholder"

    def parse_frame(self, raw_frame: str) -> ParsedStreamDelta:
        cleaned = self._strip_framing(raw_frame)
        if not cleaned:
            return ParsedStreamDelta()

        extracted_text = None
        extracted_conv_id = None
        extracted_cont_token = None

        # 1. Attempt JSON parsing of WebChannel array [[seq, [payload]]]
        try:
            data = json.loads(cleaned, strict=False)
            strings = list(self._find_strings(data))
            
            # Look for conversation ID and continuation token
            for s in strings:
                if not extracted_conv_id and self.CONV_ID_PATTERN.match(s):
                    extracted_conv_id = s
                elif not extracted_cont_token and self.CONT_TOKEN_PATTERN.match(s):
                    extracted_cont_token = s

            # Check if any string contains base64 protobuf or nested JSON
            proto_text_found = False
            for s in strings:
                if len(s) > 20 and not s.startswith(("http", "c_", "noop", "CgA")):
                    # Try base64 protobuf decoding
                    try:
                        b = base64.b64decode(s)
                        fields = ProtobufReader.parse(b)
                        if fields:
                            # 1. Deterministic direct path lookup
                            c_id = ProtobufReader.find_path(fields, [2, 7, 1, 4, 4, 2, 1])
                            if c_id and isinstance(c_id, str):
                                extracted_conv_id = c_id

                            p_text = ProtobufReader.find_path(fields, [2, 7, 1, 4, 4, 5, 2, 1])
                            if p_text and isinstance(p_text, str):
                                extracted_text = p_text
                                proto_text_found = True

                            c_tok = ProtobufReader.find_path(fields, [2, 7, 1, 4, 4, 26])
                            if c_tok and isinstance(c_tok, str):
                                extracted_cont_token = c_tok

                            # 2. Fallback heuristic for any missing fields
                            if not extracted_conv_id or not extracted_cont_token:
                                for f in fields:
                                    for sub_s in self._find_proto_strings(f):
                                        if not extracted_conv_id and self.CONV_ID_PATTERN.match(sub_s):
                                            extracted_conv_id = sub_s
                                        elif not extracted_cont_token and self.CONT_TOKEN_PATTERN.match(sub_s):
                                            extracted_cont_token = sub_s
                    except Exception:
                        pass
                
                # Check for direct text candidates (for non-protobuf test fixtures)
                if not proto_text_found and s not in ("noop", "CgA="):
                    if len(s) > 3 and not s.startswith(("http", "//", "c_", "Aw", "rc_", "r_")):
                        if not re.match(r"^[0-9a-f-]{30,}$", s, re.I) and not re.match(r"^[A-Z0-9_-]{20,}$", s):
                            if not re.match(r"^[A-Za-z0-9+/=]{40,}$", s):
                                if not extracted_text or len(s) > len(extracted_text):
                                    extracted_text = s

        except Exception:
            # Fallback if raw frame is not standard JSON
            for token in cleaned.split():
                if self.CONV_ID_PATTERN.match(token):
                    extracted_conv_id = token
                elif self.CONT_TOKEN_PATTERN.match(token):
                    extracted_cont_token = token

        # Compute delta
        delta_text = None
        if extracted_text:
            if extracted_text.startswith(self.last_content):
                delta_text = extracted_text[len(self.last_content):]
                self.last_content = extracted_text
            elif extracted_text != self.last_content:
                delta_text = extracted_text
                self.last_content = extracted_text

        return ParsedStreamDelta(
            text=delta_text if delta_text else None,
            conversation_id=extracted_conv_id,
            continuation_token=extracted_cont_token,
        )

    def _find_proto_strings(self, field: ProtoField) -> Iterator[str]:
        if isinstance(field.value, str):
            yield field.value
        elif isinstance(field.value, list):
            for sub in field.value:
                if isinstance(sub, ProtoField):
                    yield from self._find_proto_strings(sub)

    def extract_image_candidates(self, raw_chunk: str) -> List[str]:
        urls = self.IMAGE_URL_PATTERN.findall(raw_chunk)
        # Deduplicate preserving order
        seen = set()
        unique = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    def is_end_of_stream(self, raw_chunk: str) -> bool:
        s = raw_chunk.strip()
        try:
            cleaned = self._strip_framing(s)
            data = json.loads(cleaned, strict=False)
            if isinstance(data, list) and len(data) > 0:
                for item in data:
                    if isinstance(item, list) and len(item) > 1:
                        payload = item[1]
                        if payload == ["close"] or payload == ["c", "close"] or payload == ["stop"]:
                            return True
        except Exception:
            pass
        return '["close"]' in s or '["c","close"]' in s
