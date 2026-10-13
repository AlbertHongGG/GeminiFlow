import json
import unittest
from gemini_flow.domain.models import ModelSpec, ModelFamily, ThinkingLevel
from gemini_flow.domain.entities import ChatRequest, GeminiTokens, SessionData
from gemini_flow.infrastructure.clients.gemini_api.protocol import GeminiProtocolEngine
from gemini_flow.config import REQUEST_BL_PARAM

class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.engine = GeminiProtocolEngine(server_bl=REQUEST_BL_PARAM)
        self.tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="123456789")

    def test_case_1_flash_thinking_low(self):
        """Case 1: gemini-3.8-flash (thinking low) -> p79=1, p80=1"""
        req = ChatRequest(prompt="第一次測試", model="gemini-3.8-flash", thinking="low")
        proto = self.engine.build_request(req, self.tokens, turn_index=0)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(h525[4], "56fdd199312815e2")
        self.assertEqual(h525[14], 1)
        self.assertEqual(h525[15], 1)  # Low thinking
        self.assertEqual(inner[17], [[0]])
        self.assertEqual(inner[79], 1)
        self.assertEqual(inner[80], 1)

    def test_case_2_flash_thinking_medium(self):
        """Case 2: gemini-3.8-flash (thinking medium) -> p79=1, p80=4"""
        req = ChatRequest(prompt="第二次測試", model="gemini-3.8-flash", thinking="medium")
        proto = self.engine.build_request(req, self.tokens, turn_index=1)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(h525[4], "56fdd199312815e2")
        self.assertEqual(h525[14], 1)
        self.assertEqual(h525[15], 4)  # Medium thinking = 4
        self.assertEqual(inner[17], [[1]])
        self.assertEqual(inner[79], 1)
        self.assertEqual(inner[80], 4)

    def test_case_3_flash_thinking_high(self):
        """Case 3: gemini-3.8-flash (thinking high) -> p79=1, p80=2"""
        req = ChatRequest(prompt="第三次測試", model="gemini-3.8-flash", thinking="high")
        proto = self.engine.build_request(req, self.tokens, turn_index=2)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(h525[4], "56fdd199312815e2")
        self.assertEqual(h525[14], 1)
        self.assertEqual(h525[15], 2)  # High thinking = 2
        self.assertEqual(inner[17], [[2]])
        self.assertEqual(inner[79], 1)
        self.assertEqual(inner[80], 2)

    def test_case_4_pro_thinking_high(self):
        """Case 4: gemini-3-pro (thinking high) -> p79=3, p80=2"""
        req = ChatRequest(prompt="第四次測試", model="gemini-3-pro", thinking="high")
        proto = self.engine.build_request(req, self.tokens, turn_index=3)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(h525[4], "e6fa609c3fa255c0")
        self.assertEqual(h525[14], 3)
        self.assertEqual(h525[15], 2)  # High thinking = 2
        self.assertEqual(inner[17], [[3]])
        self.assertEqual(inner[79], 3)
        self.assertEqual(inner[80], 2)

    def test_multi_turn_conversation_ids_preservation(self):
        """Ensure conversation tracking continues to populate arr[2] without breakage"""
        conv_ids = ["c_test_conv", "r_test_resp", "rc_test_choice"]
        req = ChatRequest(prompt="延續對話", model="gemini-3.8-flash")
        proto = self.engine.build_request(req, self.tokens, conversation_ids=conv_ids, turn_index=1)

        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertIsNotNone(inner[2])
        self.assertEqual(inner[2][0], "c_test_conv")
        self.assertEqual(inner[2][1], "r_test_resp")
        self.assertEqual(inner[2][2], "rc_test_choice")

if __name__ == "__main__":
    unittest.main()
