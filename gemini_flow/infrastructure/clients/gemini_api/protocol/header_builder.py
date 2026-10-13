from __future__ import annotations
import json
import time
import random
from typing import Dict, Optional, List
from gemini_flow.domain.models import ModelSpec

class JspbHeaderBuilder:
    """
    Constructs Google's JSPB extension headers (x-goog-ext-*-jspb)
    using structured, typed arrays rather than string template formatting.
    """

    CAPABILITIES = [4, 5, 6, 8, 16, 19, 20, 4, 5, 6, 8, 16, 19, 20]

    def __init__(
        self,
        model_spec: ModelSpec,
        session_uuid: str,
        req_uuid: str,
        server_bl: str,
    ):
        self.model_spec = model_spec
        self.session_uuid = session_uuid
        self.req_uuid = req_uuid
        self.server_bl = server_bl

    def build_525001261(self) -> str:
        """
        Builds the 20-element model routing & client capabilities header:
        x-goog-ext-525001261-jspb
        """
        arr: List[Optional[object]] = [None] * 20
        arr[0] = 1
        arr[4] = self.model_spec.model_hash
        arr[7] = 0
        arr[8] = self.CAPABILITIES
        arr[11] = 2
        arr[14] = self.model_spec.model_id
        arr[15] = self.model_spec.thinking_level
        arr[16] = self.session_uuid
        arr[17] = [self.server_bl]
        
        # Emulate high-resolution client clock pair [seconds, nanos]
        now = time.time()
        sec = int(now)
        nsec = int((now - sec) * 1_000_000_000)
        arr[19] = [[random.randint(1, 5), random.randint(100_000_000, 999_000_000)], [sec, nsec]]

        return json.dumps(arr, separators=(",", ":"))

    def build_525005358(self) -> str:
        """
        Builds the request correlation UUID header:
        x-goog-ext-525005358-jspb: ["<REQ_UUID>", 1]
        """
        return json.dumps([self.req_uuid, 1], separators=(",", ":"))

    def build_all_headers(self) -> Dict[str, str]:
        """
        Returns all jspb extension headers.
        """
        return {
            "x-goog-ext-525001261-jspb": self.build_525001261(),
            "x-goog-ext-525005358-jspb": self.build_525005358(),
            "x-goog-ext-73010989-jspb": "[0]",
            "x-goog-ext-73010990-jspb": "[0,0,0]",
        }
