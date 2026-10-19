import unittest
import base64
from gemini_flow.infrastructure.protocol.protobuf import (
    ProtobufBuilder,
    ProtobufReader,
    encode_varint,
    decode_varint,
)

class TestProtobufWire(unittest.TestCase):
    def test_varint_encode_decode(self):
        cases = [0, 1, 127, 128, 300, 16384, 2147483647, 0x1234567890ABCDEF]
        for c in cases:
            b = encode_varint(c)
            decoded, offset = decode_varint(b, 0)
            self.assertEqual(decoded, c)
            self.assertEqual(offset, len(b))

    def test_prompt_packet_exact_match(self):
        """
        Verify that encoding the prompt message matches the exact byte sequence
        captured in Turn 4 (第四次測試) from 10_20_session1.json.
        """
        # Captured from Entry 162 in 10_20_session1.json:
        # req0___data__ = 'EhUIAUoRCg/nrKzlm5vmrKHmuKzoqaY='
        expected_raw = base64.b64decode("EhUIAUoRCg/nrKzlm5vmrKHmuKzoqaY=")
        
        # Build prompt using ProtobufBuilder:
        # Tag 2 -> Tag 1 (varint 1), Tag 9 -> Tag 1 (string "第四次測試")
        sub_text = ProtobufBuilder().add_string(1, "第四次測試")
        container = ProtobufBuilder().add_varint(1, 1).add_message(9, sub_text)
        root = ProtobufBuilder().add_message(2, container)
        built_raw = root.build()
        
        self.assertEqual(built_raw, expected_raw)
        self.assertEqual(root.to_base64(), "EhUIAUoRCg/nrKzlm5vmrKHmuKzoqaY=")

    def test_ack_packet_exact_match(self):
        """
        Verify that encoding the ack packet matches Turn 4 Entry 185:
        req0___data__ = 'IgIIAQ==' -> b'"\x02\x08\x01'
        Tag 4 -> Tag 1: 1
        """
        expected_raw = base64.b64decode("IgIIAQ==")
        sub = ProtobufBuilder().add_varint(1, 1)
        root = ProtobufBuilder().add_message(4, sub)
        self.assertEqual(root.build(), expected_raw)
        self.assertEqual(root.to_base64(), "IgIIAQ==")

    def test_reader_find_path(self):
        raw = base64.b64decode("EhUIAUoRCg/nrKzlm5vmrKHmuKzoqaY=")
        fields = ProtobufReader.parse(raw)
        prompt = ProtobufReader.find_path(fields, [2, 9, 1])
        self.assertEqual(prompt, "第四次測試")
