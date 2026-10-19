from __future__ import annotations
import struct
from typing import Tuple

WIRE_VARINT = 0
WIRE_FIXED64 = 1
WIRE_LENGTH_DELIMITED = 2
WIRE_START_GROUP = 3  # Deprecated
WIRE_END_GROUP = 4    # Deprecated
WIRE_FIXED32 = 5

def encode_varint(value: int) -> bytes:
    """Encodes an integer into standard unsigned Protobuf Varint bytes."""
    if value < 0:
        # Standard Protobuf treats negative ints as two's complement 64-bit varints (10 bytes)
        value &= (1 << 64) - 1
    bits = value & 0x7F
    value >>= 7
    chunks = bytearray()
    while value:
        chunks.append(0x80 | bits)
        bits = value & 0x7F
        value >>= 7
    chunks.append(bits)
    return bytes(chunks)

def decode_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
    """Decodes a Varint from bytes starting at offset. Returns (value, next_offset)."""
    res = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise IndexError("Unexpected end of data while decoding varint")
        b = data[offset]
        offset += 1
        res |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return res, offset

def encode_tag(field_number: int, wire_type: int) -> bytes:
    """Encodes field_number and wire_type into a Protobuf tag."""
    if field_number < 1:
        raise ValueError("Protobuf field numbers must be greater than 0")
    key = (field_number << 3) | (wire_type & 0x07)
    return encode_varint(key)

def decode_tag(data: bytes, offset: int = 0) -> Tuple[int, int, int]:
    """Decodes (field_number, wire_type, next_offset) from data at offset."""
    key, next_offset = decode_varint(data, offset)
    field_number = key >> 3
    wire_type = key & 0x07
    return field_number, wire_type, next_offset

def encode_fixed32(value: int) -> bytes:
    return struct.pack("<I", value & 0xFFFFFFFF)

def decode_fixed32(data: bytes, offset: int = 0) -> Tuple[int, int]:
    if offset + 4 > len(data):
        raise IndexError("Unexpected end of data while decoding fixed32")
    val = struct.unpack("<I", data[offset:offset+4])[0]
    return val, offset + 4

def encode_fixed64(value: int) -> bytes:
    return struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)

def decode_fixed64(data: bytes, offset: int = 0) -> Tuple[int, int]:
    if offset + 8 > len(data):
        raise IndexError("Unexpected end of data while decoding fixed64")
    val = struct.unpack("<Q", data[offset:offset+8])[0]
    return val, offset + 8
