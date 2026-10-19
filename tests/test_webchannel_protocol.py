import unittest
import base64
from gemini_flow.domain.models import ModelSpec
from gemini_flow.domain.entities import ChatRequest, GeminiCredentials, SessionData
from gemini_flow.infrastructure.protocol.protobuf import ProtobufReader
from gemini_flow.infrastructure.clients.gemini_api.protocol import (
    WebChannelHeaderBuilder,
    WebChannelPayloadBuilder,
    WebChannelProtocolEngine,
)

class TestWebChannelProtocol(unittest.TestCase):
    def setUp(self):
        self.cookies = {"SAPISID": "test_sapisid_secret"}
        self.creds = GeminiCredentials(
            cookies=self.cookies,
            server_bl="boq_gemini-web-uiserver_20261016.00_p0",
        )

    def test_header_builder(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="low")
        builder = WebChannelHeaderBuilder(
            model_spec=spec,
            session_uuid="SESS-UUID-123",
            req_uuid="REQ-UUID-456",
            server_bl=self.creds.server_bl,
        )

        # 525001261-bin
        h525_b64 = builder.build_525001261_bin()
        fields = ProtobufReader.parse(base64.b64decode(h525_b64))
        self.assertEqual(ProtobufReader.find_field(fields, 1), 1)
        self.assertEqual(ProtobufReader.find_field(fields, 5), "56fdd199312815e2")
        self.assertEqual(ProtobufReader.find_field(fields, 15), 1)
        self.assertEqual(ProtobufReader.find_field(fields, 16), 1)
        self.assertEqual(ProtobufReader.find_path(fields, [18, 1]), "boq_gemini-web-uiserver_20261016.00_p0")

        # 525005358-bin
        h5358_b64 = builder.build_525005358_bin()
        fields_5358 = ProtobufReader.parse(base64.b64decode(h5358_b64))
        self.assertEqual(ProtobufReader.find_field(fields_5358, 1), "REQ-UUID-456")
        self.assertEqual(ProtobufReader.find_field(fields_5358, 2), 1)

        # Tunnel headers
        tunnel = builder.build_tunnel_http_headers(
            authorization="SAPISIDHASH test_token",
            api_key="test_api_key",
        )
        self.assertIn("Authorization:SAPISIDHASH test_token", tunnel)
        self.assertIn("X-Goog-Api-Key:test_api_key", tunnel)
        self.assertIn("x-goog-ext-525001261-bin:", tunnel)
        self.assertIn("x-goog-ext-525005358-bin:", tunnel)
        self.assertIn("X-WebChannel-Content-Type:application/x-protobuf", tunnel)

    def test_payload_builder_all_phases(self):
        spec = ModelSpec.resolve("gemini-3-pro", thinking="low")
        builder = WebChannelPayloadBuilder(
            prompt="測試提示詞",
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-999",
            conversation_id="c_test123",
            continuation_token="token_xyz",
            turn_index=1,
        )

        # 1. ofs=0 (metadata)
        init_b64 = builder.build_metadata_payload()
        init_fields = ProtobufReader.parse(base64.b64decode(init_b64))
        inner_fields = ProtobufReader.find_path(init_fields, [1, 8, 5, 1])
        self.assertIsNotNone(inner_fields)
        self.assertEqual(ProtobufReader.find_field(inner_fields, 80), 3)  # Pro model_id = 3
        self.assertEqual(ProtobufReader.find_field(inner_fields, 81), 1)  # thinking_level = 1
        self.assertEqual(ProtobufReader.find_path(inner_fields, [18, 1, 1]), 1)  # turn_index = 1
        self.assertEqual(ProtobufReader.find_field(inner_fields, 97), 1)  # continuation session = 1
        self.assertEqual(ProtobufReader.find_path(inner_fields, [72, 1]), "c_test123")
        self.assertEqual(ProtobufReader.find_path(inner_fields, [72, 8]), "token_xyz")

        # 2. ofs=1 (prompt)
        prompt_b64 = builder.build_prompt_payload()
        prompt_fields = ProtobufReader.parse(base64.b64decode(prompt_b64))
        extracted_prompt = ProtobufReader.find_path(prompt_fields, [2, 9, 1])
        self.assertEqual(extracted_prompt, "測試提示詞")

        # 3. ofs=2 (ack)
        ack_b64 = builder.build_ack_payload()
        ack_fields = ProtobufReader.parse(base64.b64decode(ack_b64))
        self.assertEqual(ProtobufReader.find_path(ack_fields, [4, 1]), 1)

    def test_protocol_engine_plan_5_turns(self):
        engine = WebChannelProtocolEngine()
        
        # Turn 1: Flash Low
        plan1 = engine.plan_turn(
            request=ChatRequest(prompt="第一次測試", model="gemini-3.8-flash", thinking="low"),
            credentials=self.creds,
            session_data=None,
        )
        self.assertEqual(plan1.handshake_params["VER"], "8")
        self.assertEqual(plan1.handshake_data["count"], "0")
        init1 = ProtobufReader.parse(base64.b64decode(plan1.payload_builder.build_metadata_payload()))
        inner1 = ProtobufReader.find_path(init1, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_field(inner1, 80), 1)
        self.assertEqual(ProtobufReader.find_field(inner1, 81), 1)
        self.assertEqual(ProtobufReader.find_field(inner1, 97), 0)  # new session = 0

        # Turn 4: Argon Medium
        sess4 = SessionData(session_id="s4", conversation_id="c_1", turn_index=3)
        plan4 = engine.plan_turn(
            request=ChatRequest(prompt="第四次測試", model="gemini4Argon", thinking="medium"),
            credentials=self.creds,
            session_data=sess4,
        )
        init4 = ProtobufReader.parse(base64.b64decode(plan4.payload_builder.build_metadata_payload()))
        inner4 = ProtobufReader.find_path(init4, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_field(inner4, 80), 8)
        self.assertEqual(ProtobufReader.find_field(inner4, 81), 4)
        self.assertEqual(ProtobufReader.find_field(inner4, 97), 1)  # continuation session = 1

    def test_check_control_error_401(self):
        from gemini_flow.infrastructure.clients.gemini_api.webchannel_parser import WebChannelStreamParser
        from gemini_flow.domain.exceptions import AuthenticationError

        parser = WebChannelStreamParser()
        rpc_401_payload = '145\n[[1, {"__sm__": {"status": [[{"error": {"code": 401, "message": "Request is missing valid authentication credentials."}}]]}}]]\n'
        with self.assertRaises(AuthenticationError) as cm:
            parser.check_control_error(rpc_401_payload)
        self.assertIn("401", str(cm.exception))

    def test_check_control_error_429(self):
        from gemini_flow.infrastructure.clients.gemini_api.webchannel_parser import WebChannelStreamParser
        from gemini_flow.domain.exceptions import RateLimitError

        parser = WebChannelStreamParser()
        rpc_429_payload = '110\n[[1, {"__sm__": {"status": [[{"error": {"code": 429, "message": "RESOURCE_EXHAUSTED"}}]]}}]]\n'
        with self.assertRaises(RateLimitError) as cm:
            parser.check_control_error(rpc_429_payload)
        self.assertIn("429", str(cm.exception))

    def test_byte_level_chunk_framing_multibyte_utf8(self):
        """
        Tests that when Chinese/multibyte characters are split across TCP chunk boundaries,
        the byte-level framer does not corrupt characters or miscalculate frame length.
        """
        import re

        # Chinese string where each char is 3 bytes in UTF-8: "這是一段繁體中文測試訊息！" (13 chars * 3 = 39 bytes + quotes/brackets)
        json_frame = '[1, ["這是一段繁體中文測試訊息！🎉"]]'
        raw_bytes = json_frame.encode("utf-8")
        byte_len = len(raw_bytes)
        
        full_wire_packet = f"{byte_len}\n".encode("ascii") + raw_bytes + b"\n"

        # Split across an arbitrary byte position right in the middle of a 3-byte Chinese character or 4-byte emoji
        split_pos = 12
        chunk1 = full_wire_packet[:split_pos]
        chunk2 = full_wire_packet[split_pos:]

        buffer = bytearray()
        yielded_frames = []

        for chunk in [chunk1, chunk2]:
            buffer.extend(chunk)
            while buffer:
                match = re.search(rb"^(\d+)\s*\n", buffer)
                if match:
                    header_len = match.end()
                    frame_len = int(match.group(1).decode("ascii"))
                    total_needed = header_len + frame_len
                    if len(buffer) < total_needed:
                        break
                    frame_bytes = bytes(buffer[header_len:total_needed])
                    buffer = buffer[total_needed:]
                    while buffer and buffer[:1] in (b"\r", b"\n"):
                        del buffer[0]
                    yielded_frames.append(frame_bytes.decode("utf-8", errors="replace"))
                else:
                    break

        self.assertEqual(len(yielded_frames), 1)
        self.assertEqual(yielded_frames[0], json_frame)
        self.assertIn("這是一段繁體中文測試訊息！🎉", yielded_frames[0])

