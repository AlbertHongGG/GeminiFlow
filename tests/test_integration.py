import unittest
import base64
from gemini_flow.domain.models import ModelSpec
from gemini_flow.domain.entities import ChatRequest, GeminiCredentials, SessionData
from gemini_flow.infrastructure.protocol.protobuf import ProtobufReader
from gemini_flow.infrastructure.clients.gemini_api.protocol import WebChannelProtocolEngine
from gemini_flow.config import REQUEST_BL_PARAM

class TestIntegration(unittest.TestCase):
    """
    Validates the 5 turns recorded in the October 20, 2026 WebChannel packet captures
    (10_20_session1.json and 10_20_session2.json).
    """
    def setUp(self):
        self.engine = WebChannelProtocolEngine(default_server_bl=REQUEST_BL_PARAM)
        self.creds = GeminiCredentials(
            cookies={"SAPISID": "test_sapisid_secret_123"},
            server_bl=REQUEST_BL_PARAM,
        )

    def test_turn_1_flash_thinking_low(self):
        """
        Turn 1: gemini3.8Flash (think mode is low) "第一次測試"
        - New session (turn 0)
        - model_id = 1, model_hash = "56fdd199312815e2", thinking_level = 1
        - Tag 97 = 0, Tag 72 = None
        """
        req = ChatRequest(prompt="第一次測試", model="gemini-3.8-flash", thinking="low")
        plan = self.engine.plan_turn(req, self.creds, session_data=None)

        # Handshake
        self.assertEqual(plan.handshake_params["VER"], "8")
        self.assertEqual(plan.handshake_params["CVER"], "22")
        self.assertEqual(plan.handshake_data["count"], "0")

        # Header 525001261-bin
        h525 = ProtobufReader.parse(base64.b64decode(plan.header_builder.build_525001261_bin()))
        self.assertEqual(ProtobufReader.find_field(h525, 5), "56fdd199312815e2")
        self.assertEqual(ProtobufReader.find_field(h525, 15), 1)
        self.assertEqual(ProtobufReader.find_field(h525, 16), 1)

        # Metadata ofs=0
        init_raw = base64.b64decode(plan.payload_builder.build_metadata_payload())
        init_fields = ProtobufReader.parse(init_raw)
        inner = ProtobufReader.find_path(init_fields, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 0)  # turn index 0
        self.assertIsNone(ProtobufReader.find_field(inner, 72))  # no continuation context
        self.assertEqual(ProtobufReader.find_field(inner, 80), 1)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 1)
        self.assertEqual(ProtobufReader.find_field(inner, 97), 0)

        # Prompt ofs=1
        prompt_raw = base64.b64decode(plan.payload_builder.build_prompt_payload())
        prompt_fields = ProtobufReader.parse(prompt_raw)
        self.assertEqual(ProtobufReader.find_path(prompt_fields, [2, 9, 1]), "第一次測試")

    def test_turn_2_pro_thinking_low(self):
        """
        Turn 2: gemini3Pro (think mode is low) "第二次測試"
        - Continuing session (turn 1)
        - model_id = 3, model_hash = "e6fa609c3fa255c0", thinking_level = 1
        - Tag 97 = 1, Tag 72 = [conv_id, None*6, token]
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_039565bc090b6979",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZS5cPttExo",
            turn_index=1,
        )
        req = ChatRequest(prompt="第二次測試", model="gemini-3-pro", thinking="low")
        plan = self.engine.plan_turn(req, self.creds, session_data=session)

        h525 = ProtobufReader.parse(base64.b64decode(plan.header_builder.build_525001261_bin()))
        self.assertEqual(ProtobufReader.find_field(h525, 5), "e6fa609c3fa255c0")
        self.assertEqual(ProtobufReader.find_field(h525, 15), 3)  # Pro model_id = 3
        self.assertEqual(ProtobufReader.find_field(h525, 16), 1)

        init = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_metadata_payload()))
        inner = ProtobufReader.find_path(init, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 1)  # turn index 1
        self.assertEqual(ProtobufReader.find_path(inner, [72, 1]), "c_039565bc090b6979")
        self.assertEqual(ProtobufReader.find_path(inner, [72, 8]), "AwAAAAAAAAAQANM7mBjXKZS5cPttExo")
        self.assertEqual(ProtobufReader.find_field(inner, 80), 3)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 1)
        self.assertEqual(ProtobufReader.find_field(inner, 97), 1)

        prompt = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_prompt_payload()))
        self.assertEqual(ProtobufReader.find_path(prompt, [2, 9, 1]), "第二次測試")

    def test_turn_3_argon_thinking_low(self):
        """
        Turn 3: gemini4Argon (think mode is low) "第三次測試"
        - Continuing session (turn 2)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 1
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_039565bc090b6979",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZT52i1uExo",
            turn_index=2,
        )
        req = ChatRequest(prompt="第三次測試", model="gemini4Argon", thinking="low")
        plan = self.engine.plan_turn(req, self.creds, session_data=session)

        h525 = ProtobufReader.parse(base64.b64decode(plan.header_builder.build_525001261_bin()))
        self.assertEqual(ProtobufReader.find_field(h525, 5), "95a4c0abcba24364")
        self.assertEqual(ProtobufReader.find_field(h525, 15), 8)
        self.assertEqual(ProtobufReader.find_field(h525, 16), 1)

        init = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_metadata_payload()))
        inner = ProtobufReader.find_path(init, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 2)
        self.assertEqual(ProtobufReader.find_field(inner, 80), 8)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 1)
        self.assertEqual(ProtobufReader.find_field(inner, 97), 1)

    def test_turn_4_argon_thinking_medium(self):
        """
        Turn 4: gemini4Argon (think mode is medium) "第四次測試"
        - Continuing session (turn 3)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 4
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_039565bc090b6979",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZT52i1uExo",
            turn_index=3,
        )
        req = ChatRequest(prompt="第四次測試", model="gemini4Argon", thinking="medium")
        plan = self.engine.plan_turn(req, self.creds, session_data=session)

        h525 = ProtobufReader.parse(base64.b64decode(plan.header_builder.build_525001261_bin()))
        self.assertEqual(ProtobufReader.find_field(h525, 15), 8)
        self.assertEqual(ProtobufReader.find_field(h525, 16), 4)  # thinking_level = 4

        init = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_metadata_payload()))
        inner = ProtobufReader.find_path(init, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 3)
        self.assertEqual(ProtobufReader.find_field(inner, 80), 8)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 4)

        prompt = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_prompt_payload()))
        self.assertEqual(ProtobufReader.find_path(prompt, [2, 9, 1]), "第四次測試")

    def test_turn_5_argon_thinking_high(self):
        """
        Turn 5: gemini4Argon (think mode is high) "第五次測試"
        - Continuing session (turn 4)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 2
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_039565bc090b6979",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZT52i1uExo",
            turn_index=4,
        )
        req = ChatRequest(prompt="第五次測試", model="gemini4Argon", thinking="high")
        plan = self.engine.plan_turn(req, self.creds, session_data=session)

        h525 = ProtobufReader.parse(base64.b64decode(plan.header_builder.build_525001261_bin()))
        self.assertEqual(ProtobufReader.find_field(h525, 15), 8)
        self.assertEqual(ProtobufReader.find_field(h525, 16), 2)  # thinking_level = 2

        init = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_metadata_payload()))
        inner = ProtobufReader.find_path(init, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 4)
        self.assertEqual(ProtobufReader.find_field(inner, 80), 8)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 2)

        prompt = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_prompt_payload()))
        self.assertEqual(ProtobufReader.find_path(prompt, [2, 9, 1]), "第五次測試")

if __name__ == "__main__":
    unittest.main()
