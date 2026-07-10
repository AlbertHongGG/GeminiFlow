import json
from typing import Any, Iterator, Optional, Sequence, Tuple, List

class ResponseParser:
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

    def extract_text_delta(self, raw_line: str) -> Tuple[Optional[str], Optional[List[str]]]:
        """Extract incremental text delta and conversation IDs from one StreamGenerate response line.
        Returns (delta, ids).
        """
        try:
            line = json.loads(raw_line)
        except Exception:
            return None, None
            
        if not isinstance(line, list) or not line:
            return None, None

        try:
            if len(line[0]) < 3 or not line[0][2]:
                return None, None
            response_part = json.loads(line[0][2])
            if not response_part:
                return None, None
        except Exception:
            return None, None

        ids = None
        try:
            if len(response_part) > 1 and isinstance(response_part[1], list) and response_part[1]:
                if isinstance(response_part[1][0], str) and response_part[1][0].startswith("c_"):
                    ids = response_part[1]
        except Exception:
            pass

        try:
            if len(response_part) < 5:
                return None, ids
            content = self.extract_content(response_part)
            if not content:
                return None, ids
        except Exception:
            return None, ids

        if self.last_content and content.startswith(self.last_content):
            delta = content[len(self.last_content):]
            self.last_content = content
            return delta, ids
            
        self.last_content = content
        return content, ids

    def extract_image_candidates(self, raw_line: str) -> Sequence[str]:
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

        import re
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
        """
        Classifies an image URL as either a 'placeholder' or 'output'.
        Returns 'placeholder', 'output', or None if neither.
        """
        import re
        _CONTROL_RE = re.compile(r"[\x00-\x1F\x7F\u200B\u200C\u200D\uFEFF]")
        norm = _CONTROL_RE.sub("", url.strip())
        if not norm:
            return None
            
        if "googleusercontent.com/image_generation_content/" in norm or ("lh3.googleusercontent.com/gg/" in norm and "lh3.googleusercontent.com/gg-dl/" not in norm):
            return "placeholder"
        if norm.startswith("data:image/") or "lh3.googleusercontent.com/gg-dl/" in norm:
            return "output"
        return None
