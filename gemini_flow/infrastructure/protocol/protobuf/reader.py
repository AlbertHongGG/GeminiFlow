from __future__ import annotations
from typing import List, Tuple, Any, Optional
from .wire import (
    WIRE_VARINT,
    WIRE_FIXED64,
    WIRE_LENGTH_DELIMITED,
    WIRE_FIXED32,
    decode_tag,
    decode_varint,
    decode_fixed32,
    decode_fixed64,
)

class ProtoField:
    __slots__ = ("tag", "wire_type", "value")

    def __init__(self, tag: int, wire_type: int, value: Any):
        self.tag = tag
        self.wire_type = wire_type
        self.value = value

    @property
    def is_message(self) -> bool:
        return isinstance(self.value, list)

    def __repr__(self) -> str:
        return f"ProtoField(tag={self.tag}, type={self.wire_type}, value={self.value!r})"


class ProtobufReader:
    """
    Lightweight, deterministic Protobuf binary reader.
    Accurately distinguishes embedded submessages from raw UTF-8 strings by enforcing
    strict, complete byte consumption.
    """

    @classmethod
    def parse(cls, data: bytes, recursive: bool = True) -> List[ProtoField]:
        fields, success, offset = cls._parse_stream(data, recursive=recursive)
        return fields if success or len(fields) > 0 else []

    @classmethod
    def _parse_stream(cls, data: bytes, recursive: bool = True) -> Tuple[List[ProtoField], bool, int]:
        offset = 0
        fields: List[ProtoField] = []
        n = len(data)

        while offset < n:
            try:
                tag, wire_type, offset = decode_tag(data, offset)
            except Exception:
                return fields, False, offset

            if tag < 1 or wire_type not in (WIRE_VARINT, WIRE_FIXED64, WIRE_LENGTH_DELIMITED, WIRE_FIXED32):
                return fields, False, offset

            if wire_type == WIRE_VARINT:
                try:
                    val, offset = decode_varint(data, offset)
                    fields.append(ProtoField(tag, wire_type, val))
                except Exception:
                    return fields, False, offset
            elif wire_type == WIRE_FIXED64:
                try:
                    val, offset = decode_fixed64(data, offset)
                    fields.append(ProtoField(tag, wire_type, val))
                except Exception:
                    return fields, False, offset
            elif wire_type == WIRE_LENGTH_DELIMITED:
                try:
                    length, offset = decode_varint(data, offset)
                except Exception:
                    return fields, False, offset
                if offset + length > n:
                    return fields, False, offset
                chunk = data[offset : offset + length]
                offset += length

                # Attempt strict submessage parse on chunk:
                # Must be recursive, non-empty, and consume 100% of chunk bytes without error.
                is_submessage = False
                if recursive and length > 0:
                    sub_fields, sub_success, sub_offset = cls._parse_stream(chunk, recursive=True)
                    if sub_success and sub_offset == length and len(sub_fields) > 0:
                        fields.append(ProtoField(tag, wire_type, sub_fields))
                        is_submessage = True

                if not is_submessage:
                    # Fallback to UTF-8 string or raw bytes
                    try:
                        text = chunk.decode("utf-8")
                        fields.append(ProtoField(tag, wire_type, text))
                    except UnicodeDecodeError:
                        fields.append(ProtoField(tag, wire_type, chunk))
            elif wire_type == WIRE_FIXED32:
                try:
                    val, offset = decode_fixed32(data, offset)
                    fields.append(ProtoField(tag, wire_type, val))
                except Exception:
                    return fields, False, offset

        return fields, (offset == n), offset

    @classmethod
    def find_field(cls, fields: List[ProtoField], tag: int) -> Optional[Any]:
        for f in fields:
            if f.tag == tag:
                return f.value
        return None

    @classmethod
    def find_all(cls, fields: List[ProtoField], tag: int) -> List[Any]:
        return [f.value for f in fields if f.tag == tag]

    @classmethod
    def find_path(cls, fields: List[ProtoField], path: List[int]) -> Optional[Any]:
        cur = fields
        for idx, tag in enumerate(path):
            if not isinstance(cur, list):
                return None
            val = cls.find_field(cur, tag)
            if val is None:
                return None
            if idx == len(path) - 1:
                return val
            cur = val
        return None
