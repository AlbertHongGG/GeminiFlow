import json
import unittest
from gemini_flow.domain.models import ModelSpec, ModelFamily, ThinkingLevel
from gemini_flow.domain.entities import ChatRequest, GeminiTokens
from gemini_flow.infrastructure.clients.gemini_api.protocol import (
    JspbHeaderBuilder,
    GeminiPayloadBuilder,
    GeminiProtocolEngine,
)

class TestProtocolEngine(unittest.TestCase):
    def test_jspb_header_builder(self):
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

    def test_payload_builder_structure(self):
        spec = ModelSpec.resolve("gemini-3-pro", thinking="high")
        builder = GeminiPayloadBuilder(
            prompt="Hello Pro",
            system_prompt=None,
            language="zh-TW",
            model_spec=spec,
            req_uuid="REQ-UUID-PRO",
            turn_index=3,
        )
        arr = builder.build_inner_array()
        self.assertEqual(len(arr), 99)
        self.assertEqual(arr[0][0], "Hello Pro")
        self.assertEqual(arr[1], ["zh-TW"])
        self.assertEqual(arr[17], [[3]])  # turn index
        self.assertEqual(arr[30], [4, 16, 19])
        self.assertEqual(arr[49], 0)
        self.assertEqual(arr[59], "REQ-UUID-PRO")
        self.assertEqual(arr[61], [])
        self.assertEqual(arr[79], 3)  # Pro model ID
        self.assertEqual(arr[80], 2)  # High thinking
        self.assertEqual(arr[91], 1)
        self.assertEqual(arr[96], 1)
        self.assertEqual(arr[98], 1)

    def test_protocol_engine_integration(self):
        engine = GeminiProtocolEngine(server_bl="boq_gemini-web-uiserver_20261012.15_p0")
        req = ChatRequest(prompt="測試", model="gemini-3.8-flash", thinking="low")
        tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="123456789")

        proto_req = engine.build_request(req, tokens)
        self.assertEqual(proto_req.params["bl"], "boq_gemini-web-uiserver_20261012.15_p0")
        self.assertEqual(proto_req.params["hl"], "zh-TW")
        self.assertEqual(proto_req.params["f.sid"], "123456789")
        self.assertIn("x-goog-ext-525001261-jspb", proto_req.headers)
        self.assertEqual(proto_req.data["at"], "TEST_SNLM0E")

        f_req = json.loads(proto_req.data["f.req"])
        inner = json.loads(f_req[1])
        self.assertEqual(len(inner), 99)
        self.assertEqual(inner[79], 1)  # Flash
        self.assertEqual(inner[80], 1)  # Low thinking

if __name__ == "__main__":
    unittest.main()
