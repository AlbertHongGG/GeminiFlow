import json
import re
from typing import Any, Iterator, Optional, Sequence, Tuple, List, NamedTuple

class ParsedStreamDelta(NamedTuple):
    text: Optional[str] = None
    conversation_id: Optional[str] = None
    continuation_token: Optional[str] = None

class StreamParser:
    def __init__(self):
        self.last_content = ""

    def flatten_strings(self, value: Any) -> Iterator[str]:
        if isinstance(value, str):
            if value and not value.startswith("rc_"):
                yield value
            return
        if isinstance(value, list):
            for item in value:
                yield from self.flatten_strings(item)

    def extract_content(self, response_part: List) -> Optional[str]:
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
            candidates = list(self.flatten_strings(response_part[4]))
            if candidates:
                return max(candidates, key=len)
        except Exception:
            pass

        return None

    def extract_conversation_context(self, response_part: List) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts (conversation_id, continuation_token) from response_part.
        """
        conv_id = None
        continuation_token = None
        try:
            if len(response_part) > 1 and isinstance(response_part[1], list) and response_part[1]:
                first = response_part[1][0]
                if isinstance(first, str) and first.startswith("c_"):
                    conv_id = first
                    for item in response_part[1]:
                        if isinstance(item, str) and len(item) >= 28 and item.startswith("Aw"):
                            continuation_token = item
                            break
        except Exception:
            pass

        if conv_id and not continuation_token:
            try:
                for s in self.flatten_strings(response_part):
                    if len(s) >= 28 and s.startswith("Aw"):
                        continuation_token = s
                        break
            except Exception:
                pass

        return conv_id, continuation_token

    def extract_text_delta(self, raw_line: str) -> ParsedStreamDelta:
        try:
            line = json.loads(raw_line)
        except Exception:
            return ParsedStreamDelta()

        if not isinstance(line, list) or not line:
            return ParsedStreamDelta()

        try:
            if len(line[0]) < 3 or not line[0][2]:
                return ParsedStreamDelta()
            response_part = json.loads(line[0][2])
            if not response_part:
                return ParsedStreamDelta()
        except Exception:
            return ParsedStreamDelta()

        conv_id, continuation_token = self.extract_conversation_context(response_part)

        try:
            if len(response_part) < 5:
                return ParsedStreamDelta(text=None, conversation_id=conv_id, continuation_token=continuation_token)
            content = self.extract_content(response_part)
            if not content:
                return ParsedStreamDelta(text=None, conversation_id=conv_id, continuation_token=continuation_token)
        except Exception:
            return ParsedStreamDelta(text=None, conversation_id=conv_id, continuation_token=continuation_token)

        delta = None
        if self.last_content and content.startswith(self.last_content):
            delta = content[len(self.last_content):]
            self.last_content = content
        else:
            self.last_content = content
            delta = content

        return ParsedStreamDelta(
            text=delta,
            conversation_id=conv_id,
            continuation_token=continuation_token,
        )

    def extract_image_candidates(self, raw_line: str) -> Sequence[str]:
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

        url_regex = re.compile(r'(https?://(?:googleusercontent\.com|gstatic\.com|content-push\.googleapis\.com|lh3\.googleusercontent\.com)[^\s"\'\\]+)')

        def _extract_urls_from_text(text: str) -> Iterator[str]:
            if text.startswith("data:image/"):
                yield text
                return
            for match in url_regex.finditer(text):
                yield match.group(1)

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

        out: List[str] = []
        seen = set()
        for s in _walk_strings(response_part):
            if not s: continue
            for url in _extract_urls_from_text(s):
                if url not in seen:
                    seen.add(url)
                    out.append(url)
        return out

    def classify_image_url(self, url: str) -> Optional[str]:
        _CONTROL_RE = re.compile(r"[\x00-\x1F\x7F\u200B\u200C\u200D\uFEFF]")
        norm = _CONTROL_RE.sub("", url.strip())
        if not norm:
            return None

        if "googleusercontent.com/image_generation_content/" in norm or ("lh3.googleusercontent.com/gg/" in norm and "lh3.googleusercontent.com/gg-dl/" not in norm):
            return "placeholder"
        if norm.startswith("data:image/") or "lh3.googleusercontent.com/gg-dl/" in norm:
            return "output"
        return None
