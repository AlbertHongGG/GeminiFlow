from __future__ import annotations
import base64
from typing import Sequence, Union
from .wire import (
    WIRE_VARINT,
    WIRE_FIXED32,
    WIRE_FIXED64,
    WIRE_LENGTH_DELIMITED,
    encode_tag,
    encode_varint,
    encode_fixed32,
    encode_fixed64,
)

class ProtobufBuilder:
    """
    Lightweight, deterministic pure-Python builder for Protobuf binary wire format.
    Eliminates reliance on external protoc compiler toolchains while guaranteeing byte-level compliance.
    """

    def __init__(self) -> None:
        self._buffer = bytearray()

    def add_varint(self, field_number: int, value: int) -> ProtobufBuilder:
        self._buffer.extend(encode_tag(field_number, WIRE_VARINT))
        self._buffer.extend(encode_varint(value))
        return self

    def add_bool(self, field_number: int, value: bool) -> ProtobufBuilder:
        return self.add_varint(field_number, 1 if value else 0)

    def add_fixed32(self, field_number: int, value: int) -> ProtobufBuilder:
        self._buffer.extend(encode_tag(field_number, WIRE_FIXED32))
        self._buffer.extend(encode_fixed32(value))
        return self

    def add_fixed64(self, field_number: int, value: int) -> ProtobufBuilder:
        self._buffer.extend(encode_tag(field_number, WIRE_FIXED64))
        self._buffer.extend(encode_fixed64(value))
        return self

    def add_bytes(self, field_number: int, data: bytes) -> ProtobufBuilder:
        self._buffer.extend(encode_tag(field_number, WIRE_LENGTH_DELIMITED))
        self._buffer.extend(encode_varint(len(data)))
        self._buffer.extend(data)
        return self

    def add_string(self, field_number: int, text: str) -> ProtobufBuilder:
        return self.add_bytes(field_number, text.encode("utf-8"))

    def add_packed_varints(self, field_number: int, values: Sequence[int]) -> ProtobufBuilder:
        """Packs a repeated varint list into a single length-delimited field."""
        if not values:
            return self
        packed = bytearray()
        for v in values:
            packed.extend(encode_varint(v))
        return self.add_bytes(field_number, bytes(packed))

    def add_message(self, field_number: int, message: Union[bytes, ProtobufBuilder]) -> ProtobufBuilder:
        """Appends a sub-message (either pre-built bytes or another ProtobufBuilder)."""
        raw = message.build() if isinstance(message, ProtobufBuilder) else message
        return self.add_bytes(field_number, raw)

    def build(self) -> bytes:
        """Returns the serialized Protobuf binary payload."""
        return bytes(self._buffer)

    def to_base64(self) -> str:
        """Returns the Base64 representation of the built binary payload."""
        return base64.b64encode(self.build()).decode("ascii")

    def __len__(self) -> int:
        return len(self._buffer)

    def __repr__(self) -> str:
        return f"<ProtobufBuilder len={len(self._buffer)} hex={self._buffer[:24].hex()}...>"
