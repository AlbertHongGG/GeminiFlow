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

class TestProtocolEngine(unittest.TestCase):
    def test_webchannel_header_builder_flash(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="medium")
        builder = WebChannelHeaderBuilder(
            model_spec=spec,
            session_uuid="SESSION-UUID-123",
            req_uuid="REQ-UUID-456",
            server_bl="boq_gemini-web-uiserver_20261016.00_p0",
        )
        h525_b64 = builder.build_525001261_bin()
        fields = ProtobufReader.parse(base64.b64decode(h525_b64))

        self.assertEqual(ProtobufReader.find_field(fields, 1), 1)
        self.assertEqual(ProtobufReader.find_field(fields, 5), "56fdd199312815e2")
        self.assertEqual(ProtobufReader.find_field(fields, 15), 1)
        self.assertEqual(ProtobufReader.find_field(fields, 16), 4)  # medium thinking = 4
        self.assertEqual(ProtobufReader.find_field(fields, 17), "SESSION-UUID-123")
        self.assertEqual(ProtobufReader.find_path(fields, [18, 1]), "boq_gemini-web-uiserver_20261016.00_p0")

        h535_b64 = builder.build_525005358_bin()
        fields_5358 = ProtobufReader.parse(base64.b64decode(h535_b64))
        self.assertEqual(ProtobufReader.find_field(fields_5358, 1), "REQ-UUID-456")
        self.assertEqual(ProtobufReader.find_field(fields_5358, 2), 1)

    def test_webchannel_header_builder_argon(self):
        spec = ModelSpec.resolve("gemini4Argon", thinking="high")
        builder = WebChannelHeaderBuilder(
            model_spec=spec,
            session_uuid="SESSION-UUID-ARGON",
            req_uuid="REQ-UUID-789",
            server_bl="boq_gemini-web-uiserver_20261016.00_p0",
        )
        h525_b64 = builder.build_525001261_bin()
        fields = ProtobufReader.parse(base64.b64decode(h525_b64))

        self.assertEqual(ProtobufReader.find_field(fields, 5), "95a4c0abcba24364")
        self.assertEqual(ProtobufReader.find_field(fields, 15), 8)
        self.assertEqual(ProtobufReader.find_field(fields, 16), 2)  # high thinking = 2

    def test_payload_builder_turn_0_new_session(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="low")
        builder = WebChannelPayloadBuilder(
            prompt="第一次測試",
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-1",
            turn_index=0,
            conversation_id=None,
            continuation_token=None,
        )
        init_b64 = builder.build_metadata_payload()
        init_fields = ProtobufReader.parse(base64.b64decode(init_b64))
        inner = ProtobufReader.find_path(init_fields, [1, 8, 5, 1])

        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 0)  # turn index 0
        self.assertEqual(ProtobufReader.find_field(inner, 60), "REQ-UUID-1")
        self.assertIsNone(ProtobufReader.find_field(inner, 72))  # turn 0 has no continuation context
        self.assertEqual(ProtobufReader.find_field(inner, 80), 1)  # Flash
        self.assertEqual(ProtobufReader.find_field(inner, 81), 1)  # Low thinking
        self.assertEqual(ProtobufReader.find_field(inner, 97), 0)  # new session flag = 0

    def test_payload_builder_turn_multi_continuation(self):
        spec = ModelSpec.resolve("gemini4Argon", thinking="medium")
        builder = WebChannelPayloadBuilder(
            prompt="第四次測試",
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-4",
            turn_index=3,
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZT52i1uExo",
        )
        init_b64 = builder.build_metadata_payload()
        init_fields = ProtobufReader.parse(base64.b64decode(init_b64))
        inner = ProtobufReader.find_path(init_fields, [1, 8, 5, 1])

        self.assertEqual(ProtobufReader.find_path(inner, [18, 1, 1]), 3)  # turn index 3
        self.assertEqual(ProtobufReader.find_field(inner, 60), "REQ-UUID-4")
        self.assertEqual(ProtobufReader.find_path(inner, [72, 1]), "c_fb6da9be329112e7")
        self.assertEqual(ProtobufReader.find_path(inner, [72, 8]), "AwAAAAAAAAAQANM7mBjXKZT52i1uExo")
        self.assertEqual(ProtobufReader.find_field(inner, 80), 8)  # Argon
        self.assertEqual(ProtobufReader.find_field(inner, 81), 4)  # Medium thinking = 4
        self.assertEqual(ProtobufReader.find_field(inner, 97), 1)  # continuing session = 1

    def test_protocol_engine_plan_with_session(self):
        engine = WebChannelProtocolEngine(default_server_bl="boq_gemini-web-uiserver_20261016.00_p0")
        session = SessionData(
            session_id="sess_123",
            conversation_id="c_abc",
            continuation_token="token_xyz",
            turn_index=2,
        )
        req = ChatRequest(prompt="測試", model="gemini4Argon", thinking="high")
        creds = GeminiCredentials(
            cookies={"SAPISID": "test_sapisid"},
            server_bl="boq_gemini-web-uiserver_20261016.00_p0",
        )

        plan = engine.plan_turn(req, creds, session_data=session)
        self.assertEqual(plan.handshake_params["VER"], "8")
        self.assertEqual(plan.handshake_params["CVER"], "22")
        self.assertEqual(plan.handshake_data["count"], "0")
        self.assertIn("Authorization:SAPISIDHASH", plan.handshake_params["$httpHeaders"])

        init = ProtobufReader.parse(base64.b64decode(plan.payload_builder.build_metadata_payload()))
        inner = ProtobufReader.find_path(init, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_field(inner, 80), 8)
        self.assertEqual(ProtobufReader.find_field(inner, 81), 2)  # High thinking
        self.assertEqual(ProtobufReader.find_field(inner, 97), 1)

    def test_payload_builder_with_botguard_tokens(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="low")
        builder = WebChannelPayloadBuilder(
            prompt="測試 Botguard 注入",
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-BG",
            botguard_token="!TEST_BOTGUARD_TOKEN_STRING",
            botguard_salt="a1b2c3d4e5f60718293a4b5c6d7e8f90",
        )
        init_b64 = builder.build_metadata_payload()
        init_fields = ProtobufReader.parse(base64.b64decode(init_b64))
        inner = ProtobufReader.find_path(init_fields, [1, 8, 5, 1])
        self.assertEqual(ProtobufReader.find_field(inner, 4), "!TEST_BOTGUARD_TOKEN_STRING")
        self.assertEqual(ProtobufReader.find_field(inner, 5), "a1b2c3d4e5f60718293a4b5c6d7e8f90")

if __name__ == "__main__":
    unittest.main()
