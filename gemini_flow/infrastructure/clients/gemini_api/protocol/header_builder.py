from __future__ import annotations
import time
import random
from typing import Dict, Optional
from gemini_flow.domain.models import ModelSpec
from gemini_flow.infrastructure.protocol.protobuf import ProtobufBuilder

class WebChannelHeaderBuilder:
    """
    Constructs Google's binary WebChannel extension headers (x-goog-ext-*-bin)
    and the tunneled $httpHeaders block conforming to the latest wire protocol.
    """

    CAPABILITIES = [4, 5, 6, 8, 16, 19, 20]

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

    def build_525001261_bin(self) -> str:
        """
        Builds the binary model routing and client capabilities header:
        x-goog-ext-525001261-bin
        """
        now = time.time()
        sec = int(now)
        nsec = int((now - sec) * 1_000_000_000)

        # Submessage 18: server_bl container
        sub18 = ProtobufBuilder().add_string(1, self.server_bl)

        # Submessage 20: clock pair
        sub20_clock1 = ProtobufBuilder().add_varint(2, random.randint(1_000_000, 5_000_000))
        sub20_clock2 = ProtobufBuilder().add_varint(1, sec).add_varint(2, nsec)
        sub20 = ProtobufBuilder().add_message(1, sub20_clock1).add_message(2, sub20_clock2)

        root = ProtobufBuilder()
        root.add_varint(1, 1)
        root.add_string(5, self.model_spec.model_hash)
        root.add_varint(8, 0)
        root.add_packed_varints(9, self.CAPABILITIES)
        root.add_varint(12, 2)
        root.add_varint(15, self.model_spec.model_id)
        root.add_varint(16, self.model_spec.thinking_level)
        root.add_string(17, self.session_uuid)
        root.add_message(18, sub18)
        root.add_message(20, sub20)

        return root.to_base64()

    def build_525005358_bin(self) -> str:
        """
        Builds the request correlation UUID header:
        x-goog-ext-525005358-bin
        """
        return ProtobufBuilder().add_string(1, self.req_uuid).add_varint(2, 1).to_base64()

    def build_73010989_bin(self) -> str:
        return ProtobufBuilder().add_varint(1, 0).to_base64()

    def build_73010990_bin(self) -> str:
        return ProtobufBuilder().add_varint(1, 0).add_varint(2, 0).add_varint(3, 0).to_base64()

    def build_tunnel_http_headers(
        self,
        authorization: str,
        api_key: str,
        server_token: Optional[str] = None,
        auth_user: str = "0",
    ) -> str:
        """
        Builds the multiline RFC HTTP header block tunneled in the WebChannel handshake
        via URL query parameter $httpHeaders.
        """
        lines = [
            f"Authorization:{authorization}",
            f"X-Goog-AuthUser:{auth_user}",
            f"X-Goog-Api-Key:{api_key}",
        ]
        if server_token:
            lines.append(f"X-Server-Token:{server_token}")

        lines.extend([
            f"x-goog-ext-525001261-bin:{self.build_525001261_bin()}",
            f"x-goog-ext-73010989-bin:{self.build_73010989_bin()}",
            f"x-goog-ext-525005358-bin:{self.build_525005358_bin()}",
            f"x-goog-ext-73010990-bin:{self.build_73010990_bin()}",
            "X-WebChannel-Content-Type:application/x-protobuf",
            "",  # Final trailing CRLF
        ])
        return "\r\n".join(lines)
