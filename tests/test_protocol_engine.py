import json
import unittest
from gemini_flow.domain.models import ModelSpec, ModelFamily, ThinkingLevel
from gemini_flow.domain.entities import ChatRequest, GeminiTokens, SessionData
from gemini_flow.infrastructure.clients.gemini_api.protocol import (
    JspbHeaderBuilder,
    GeminiPayloadBuilder,
    GeminiProtocolEngine,
)

class TestProtocolEngine(unittest.TestCase):
    def test_jspb_header_builder_flash(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="medium")
        builder = JspbHeaderBuilder(
            model_spec=spec,
            session_uuid="SESSION-UUID-123",
            req_uuid="REQ-UUID-456",
            server_bl="boq_gemini-web-uiserver_20261012.15_p0",
        )
        headers = builder.build_all_headers()
        h525 = json.loads(headers["x-goog-ext-525001261-jspb"])
        h535 = json.loads(headers["x-goog-ext-525005358-jspb"])

        self.assertEqual(len(h525), 20)
        self.assertEqual(h525[0], 1)
        self.assertEqual(h525[4], "56fdd199312815e2")
        self.assertEqual(h525[8], [4, 5, 6, 8, 16, 19, 20, 4, 5, 6, 8, 16, 19, 20])
        self.assertEqual(h525[14], 1)
        self.assertEqual(h525[15], 4)  # medium thinking
        self.assertEqual(h525[16], "SESSION-UUID-123")
        self.assertEqual(h525[17], ["boq_gemini-web-uiserver_20261012.15_p0"])

        self.assertEqual(h535, ["REQ-UUID-456", 1])

    def test_jspb_header_builder_argon(self):
        spec = ModelSpec.resolve("gemini4Argon", thinking="high")
        builder = JspbHeaderBuilder(
            model_spec=spec,
            session_uuid="SESSION-UUID-ARGON",
            req_uuid="REQ-UUID-789",
            server_bl="boq_gemini-web-uiserver_20261012.15_p0",
        )
        headers = builder.build_all_headers()
        h525 = json.loads(headers["x-goog-ext-525001261-jspb"])

        self.assertEqual(h525[4], "95a4c0abcba24364")
        self.assertEqual(h525[14], 8)
        self.assertEqual(h525[15], 2)  # high thinking = 2

    def test_payload_builder_turn_0_new_session(self):
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="low")
        builder = GeminiPayloadBuilder(
            prompt="第一次測試",
            system_prompt=None,
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-1",
            turn_index=0,
            conversation_id=None,
            continuation_token=None,
        )
        arr = builder.build_inner_array()
        self.assertEqual(len(arr), 99)
        self.assertEqual(arr[0][0], "第一次測試")
        self.assertEqual(arr[1], ["zh-TW"])
        self.assertIsNone(arr[2])  # arr[2] must be None (legacy abandoned)
        self.assertEqual(arr[17], [[0]])  # turn index 0
        self.assertEqual(arr[30], [4, 16, 19])
        self.assertEqual(arr[49], 0)
        self.assertEqual(arr[59], "REQ-UUID-1")
        self.assertEqual(arr[61], [])
        self.assertIsNone(arr[71])  # turn 0 has no continuation context
        self.assertEqual(arr[79], 1)  # Flash
        self.assertEqual(arr[80], 1)  # Low thinking
        self.assertEqual(arr[91], 1)
        self.assertEqual(arr[96], 0)  # flag is 0 for turn 0
        self.assertEqual(arr[98], 1)

    def test_payload_builder_turn_multi_continuation(self):
        spec = ModelSpec.resolve("gemini4Argon", thinking="medium")
        builder = GeminiPayloadBuilder(
            prompt="第四次測試",
            system_prompt=None,
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-4",
            turn_index=3,
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZT52i1uExo",
        )
        arr = builder.build_inner_array()
        self.assertEqual(len(arr), 99)
        self.assertEqual(arr[0][0], "第四次測試")
        self.assertIsNone(arr[2])  # arr[2] is None
        self.assertEqual(arr[17], [[3]])  # turn index 3
        self.assertEqual(arr[59], "REQ-UUID-4")
        # arr[71] 8 elements: [conv_id, None, ..., token]
        self.assertEqual(
            arr[71],
            ["c_fb6da9be329112e7", None, None, None, None, None, None, "AwAAAAAAAAAQANM7mBjXKZT52i1uExo"],
        )
        self.assertEqual(arr[79], 8)  # Argon
        self.assertEqual(arr[80], 4)  # Medium thinking
        self.assertEqual(arr[96], 1)  # flag is 1 for turn > 0

    def test_protocol_engine_integration_with_session(self):
        engine = GeminiProtocolEngine(server_bl="boq_gemini-web-uiserver_20261012.15_p0")
        session = SessionData(
            session_id="sess_123",
            conversation_id="c_abc",
            continuation_token="token_xyz",
            turn_index=2,
        )
        req = ChatRequest(prompt="測試", model="gemini4Argon", thinking="high")
        tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="123456789")

        proto_req = engine.build_request(req, tokens, session_data=session)
        self.assertEqual(proto_req.params["bl"], "boq_gemini-web-uiserver_20261012.15_p0")
        self.assertEqual(proto_req.params["hl"], "zh-TW")
        self.assertEqual(proto_req.params["pageId"], "none")
        self.assertEqual(proto_req.params["f.sid"], "123456789")
        self.assertEqual(proto_req.data["at"], "TEST_SNLM0E")

        f_req = json.loads(proto_req.data["f.req"])
        inner = json.loads(f_req[1])
        self.assertEqual(len(inner), 99)
        self.assertEqual(inner[17], [[2]])
        self.assertEqual(inner[71], ["c_abc", None, None, None, None, None, None, "token_xyz"])
        self.assertEqual(inner[79], 8)
        self.assertEqual(inner[80], 2)
        self.assertEqual(inner[96], 1)

    def test_protocol_engine_with_dynamic_server_bl(self):
        engine = GeminiProtocolEngine(server_bl="boq_gemini-web-uiserver_20261012.15_p0")
        tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="123", server_bl="boq_gemini-web-uiserver_20261012.19_p1")
        req = ChatRequest(prompt="測試")
        proto = engine.build_request(req, tokens)
        self.assertEqual(proto.params["bl"], "boq_gemini-web-uiserver_20261012.19_p1")
        self.assertEqual(proto.params["pageId"], "none")
        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        self.assertEqual(h525[17], ["boq_gemini-web-uiserver_20261012.19_p1"])

if __name__ == "__main__":
    unittest.main()
