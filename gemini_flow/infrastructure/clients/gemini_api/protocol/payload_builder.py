from __future__ import annotations
import base64
from typing import Sequence, Tuple, Optional, Any, Dict
from gemini_flow.domain.models import ModelSpec
from gemini_flow.infrastructure.protocol.protobuf import ProtobufBuilder

class WebChannelPayloadBuilder:
    """
    Constructs binary Protobuf payloads for WebChannel upstream POST requests:
    - ofs=0: Session metadata & conversation context
    - ofs=1: Prompt text message payload
    - ofs=2: Finalize/Ack payload
    """

    CAPABILITIES = [4, 16, 19]

    def __init__(
        self,
        prompt: str,
        language: str,
        model_spec: ModelSpec,
        req_uuid: str,
        conversation_id: Optional[str] = None,
        continuation_token: Optional[str] = None,
        turn_index: int = 0,
        botguard_token: Optional[str] = None,
        botguard_salt: Optional[str] = None,
    ):
        self.prompt = prompt
        self.language = language
        self.model_spec = model_spec
        self.req_uuid = req_uuid
        self.conversation_id = conversation_id
        self.continuation_token = continuation_token
        self.turn_index = turn_index
        self.botguard_token = botguard_token
        self.botguard_salt = botguard_salt

    def build_metadata_payload(self) -> str:
        """
        Builds the complete Protobuf metadata payload for ofs=0.
        Returns Base64 string for req0___data__.
        """
        # 1. Inner 99-tag Core Message
        inner = ProtobufBuilder()

        # Tag 1: Prompt Container (empty text in metadata phase)
        tag1_prompt_container = (
            ProtobufBuilder()
            .add_bytes(1, b"")
            .add_varint(2, 0)
            .add_varint(7, 0)
        )
        inner.add_message(1, tag1_prompt_container)

        # Tag 2: Language
        tag2_lang = ProtobufBuilder().add_string(1, self.language)
        inner.add_message(2, tag2_lang)

        # Tag 4 & 5: Botguard Attestation and Salt
        if self.botguard_token:
            inner.add_string(4, self.botguard_token)
        if self.botguard_salt:
            inner.add_string(5, self.botguard_salt)

        # Standard static protocol flags
        tag7_box = ProtobufBuilder().add_varint(1, 0)
        inner.add_message(7, tag7_box)
        inner.add_varint(8, 1)
        inner.add_varint(11, 1)
        inner.add_varint(12, 0)

        # Tag 18: Turn index [[turn_index]]
        tag18_turn = (
            ProtobufBuilder()
            .add_message(1, ProtobufBuilder().add_varint(1, self.turn_index))
        )
        inner.add_message(18, tag18_turn)
        inner.add_varint(19, 0)
        inner.add_varint(28, 1)

        # Tag 31: Capabilities [4, 16, 19]
        inner.add_packed_varints(31, self.CAPABILITIES)

        # Static flags
        tag42_box = ProtobufBuilder().add_varint(1, 1)
        inner.add_message(42, tag42_box)
        inner.add_varint(50, 0)
        inner.add_varint(54, 0)

        # Tag 60: Request UUID
        inner.add_string(60, self.req_uuid)
        inner.add_bytes(62, b"")
        inner.add_varint(68, 0)
        inner.add_varint(69, 1)

        # Tag 72: Conversation Continuation Context
        if self.turn_index > 0 and self.conversation_id:
            tag72_conv = ProtobufBuilder().add_string(1, self.conversation_id)
            if self.continuation_token:
                tag72_conv.add_string(8, self.continuation_token)
            inner.add_message(72, tag72_conv)

        # Tag 80 & 81: Model Routing ID and Thinking Level
        inner.add_varint(80, self.model_spec.model_id)
        inner.add_varint(81, self.model_spec.thinking_level)

        # End flags
        inner.add_varint(92, 1)
        # Tag 97: 0 for new session (turn 0), 1 for continuing session (turn > 0)
        inner.add_varint(97, 0 if self.turn_index == 0 else 1)
        inner.add_varint(99, 1)

        # 2. Outer Envelope: Tag 1 -> Tag 8 -> Tag 5 -> [Tag 1 (inner), Tag 4 (1)]
        tag5_envelope = ProtobufBuilder().add_message(1, inner).add_varint(4, 1)
        tag8_envelope = ProtobufBuilder().add_message(5, tag5_envelope)

        # Session routing header block (Tag 1 of outer envelope)
        tag1_routing = (
            ProtobufBuilder()
            .add_varint(1, 1)
            .add_string(2, self.model_spec.model_hash)
            .add_string(3, self.language)
            .add_string(4, self.req_uuid)
        )

        inner_root = (
            ProtobufBuilder()
            .add_message(1, tag1_routing)
            .add_varint(2, 0)
            .add_message(8, tag8_envelope)
        )
        outer = ProtobufBuilder().add_message(1, inner_root)
        return outer.to_base64()

    def build_prompt_payload(self) -> str:
        """
        Builds the prompt text message payload for ofs=1.
        Tag 2 -> Tag 1 (varint 1), Tag 9 -> Tag 1 (string prompt)
        Returns Base64 string for req0___data__.
        """
        text_sub = ProtobufBuilder().add_string(1, self.prompt)
        container = ProtobufBuilder().add_varint(1, 1).add_message(9, text_sub)
        root = ProtobufBuilder().add_message(2, container)
        return root.to_base64()

    def build_ack_payload(self) -> str:
        """
        Builds the finalize/ack payload for ofs=2.
        Tag 4 -> Tag 1 (varint 1)
        Returns Base64 string for req0___data__.
        """
        sub = ProtobufBuilder().add_varint(1, 1)
        root = ProtobufBuilder().add_message(4, sub)
        return root.to_base64()
