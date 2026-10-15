import json
import unittest
from gemini_flow.domain.models import ModelSpec, ModelFamily, ThinkingLevel
from gemini_flow.domain.entities import ChatRequest, GeminiTokens, SessionData
from gemini_flow.infrastructure.clients.gemini_api.protocol import GeminiProtocolEngine
from gemini_flow.config import REQUEST_BL_PARAM

class TestIntegration(unittest.TestCase):
    """
    Directly validates the 5 turns recorded in the October 14, 2026 packet captures
    (10_14_session1.json and 10_14_session2.json).
    """
    def setUp(self):
        self.engine = GeminiProtocolEngine(server_bl=REQUEST_BL_PARAM)
        self.tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="123456789")

    def test_turn_1_flash_thinking_low(self):
        """
        Turn 1: gemini3.8Flash (think mode is low) "第一次測試"
        - New session (turn 0)
        - model_id = 1, model_hash = "56fdd199312815e2", thinking_level = 1
        - arr[96] = 0, arr[71] = None, arr[2] = None
        """
        req = ChatRequest(prompt="第一次測試", model="gemini-3.8-flash", thinking="low")
        proto = self.engine.build_request(req, self.tokens, session_data=None)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(proto.params["pageId"], "none")
        self.assertEqual(proto.params["bl"], REQUEST_BL_PARAM)
        self.assertEqual(h525[4], "56fdd199312815e2")
        self.assertEqual(h525[14], 1)
        self.assertEqual(h525[15], 1)
        self.assertEqual(inner[0][0], "第一次測試")
        self.assertIsNone(inner[2])
        self.assertEqual(inner[17], [[0]])
        self.assertEqual(inner[71], None)
        self.assertEqual(inner[79], 1)
        self.assertEqual(inner[80], 1)
        self.assertEqual(inner[96], 0)

    def test_turn_2_pro_thinking_low(self):
        """
        Turn 2: gemini3Pro (think mode is low) "第二次測試"
        - Continuing session (turn 1)
        - model_id = 3, model_hash = "e6fa609c3fa255c0", thinking_level = 1
        - arr[96] = 1, arr[71] = [conv_id, None, ..., token]
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZS5cPttExo",
            turn_index=1,
        )
        req = ChatRequest(prompt="第二次測試", model="gemini-3-pro", thinking="low")
        proto = self.engine.build_request(req, self.tokens, session_data=session)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(proto.params["pageId"], "none")
        self.assertEqual(proto.params["bl"], REQUEST_BL_PARAM)
        self.assertEqual(h525[4], "8c46e95b1a07cecc")
        self.assertEqual(h525[14], 6)
        self.assertEqual(h525[15], 1)
        self.assertEqual(inner[0][0], "第二次測試")
        self.assertIsNone(inner[2])
        self.assertEqual(inner[17], [[1]])
        self.assertEqual(
            inner[71],
            ["c_fb6da9be329112e7", None, None, None, None, None, None, "AwAAAAAAAAAQANM7mBjXKZS5cPttExo"],
        )
        self.assertEqual(inner[79], 6)
        self.assertEqual(inner[80], 1)
        self.assertEqual(inner[96], 1)

    def test_turn_3_argon_thinking_low(self):
        """
        Turn 3: gemini4Argon (think mode is low) "第三次測試"
        - Continuing session (turn 2)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 1
        - arr[96] = 1, arr[71] = [conv_id, None, ..., token]
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZQ5aABuExo",
            turn_index=2,
        )
        req = ChatRequest(prompt="第三次測試", model="gemini4Argon", thinking="low")
        proto = self.engine.build_request(req, self.tokens, session_data=session)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(proto.params["pageId"], "none")
        self.assertEqual(proto.params["bl"], REQUEST_BL_PARAM)
        self.assertEqual(h525[4], "95a4c0abcba24364")
        self.assertEqual(h525[14], 8)
        self.assertEqual(h525[15], 1)
        self.assertEqual(inner[0][0], "第三次測試")
        self.assertIsNone(inner[2])
        self.assertEqual(inner[17], [[2]])
        self.assertEqual(
            inner[71],
            ["c_fb6da9be329112e7", None, None, None, None, None, None, "AwAAAAAAAAAQANM7mBjXKZQ5aABuExo"],
        )
        self.assertEqual(inner[79], 8)
        self.assertEqual(inner[80], 1)
        self.assertEqual(inner[96], 1)

    def test_turn_4_argon_thinking_medium(self):
        """
        Turn 4: gemini4Argon (think mode is medium) "第四次測試"
        - Continuing session (turn 3)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 4
        - arr[96] = 1, arr[71] = [conv_id, None, ..., token]
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZSp5ANuExo",
            turn_index=3,
        )
        req = ChatRequest(prompt="第四次測試", model="gemini4Argon", thinking="medium")
        proto = self.engine.build_request(req, self.tokens, session_data=session)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(proto.params["pageId"], "none")
        self.assertEqual(proto.params["bl"], REQUEST_BL_PARAM)
        self.assertEqual(h525[4], "95a4c0abcba24364")
        self.assertEqual(h525[14], 8)
        self.assertEqual(h525[15], 4)  # medium thinking = 4
        self.assertEqual(inner[0][0], "第四次測試")
        self.assertIsNone(inner[2])
        self.assertEqual(inner[17], [[3]])
        self.assertEqual(
            inner[71],
            ["c_fb6da9be329112e7", None, None, None, None, None, None, "AwAAAAAAAAAQANM7mBjXKZSp5ANuExo"],
        )
        self.assertEqual(inner[79], 8)
        self.assertEqual(inner[80], 4)
        self.assertEqual(inner[96], 1)

    def test_turn_5_argon_thinking_high(self):
        """
        Turn 5: gemini4Argon (think mode is high) "第五次測試"
        - Continuing session (turn 4)
        - model_id = 8, model_hash = "95a4c0abcba24364", thinking_level = 2
        - arr[96] = 1, arr[71] = [conv_id, None, ..., token]
        """
        session = SessionData(
            session_id="sess_1",
            conversation_id="c_fb6da9be329112e7",
            continuation_token="AwAAAAAAAAAQANM7mBjXKZTJdQhuExo",
            turn_index=4,
        )
        req = ChatRequest(prompt="第五次測試", model="gemini4Argon", thinking="high")
        proto = self.engine.build_request(req, self.tokens, session_data=session)

        h525 = json.loads(proto.headers["x-goog-ext-525001261-jspb"])
        f_req = json.loads(proto.data["f.req"])
        inner = json.loads(f_req[1])

        self.assertEqual(proto.params["pageId"], "none")
        self.assertEqual(proto.params["bl"], REQUEST_BL_PARAM)
        self.assertEqual(h525[4], "95a4c0abcba24364")
        self.assertEqual(h525[14], 8)
        self.assertEqual(h525[15], 2)  # high thinking = 2
        self.assertEqual(inner[0][0], "第五次測試")
        self.assertIsNone(inner[2])
        self.assertEqual(inner[17], [[4]])
        self.assertEqual(
            inner[71],
            ["c_fb6da9be329112e7", None, None, None, None, None, None, "AwAAAAAAAAAQANM7mBjXKZTJdQhuExo"],
        )
        self.assertEqual(inner[79], 8)
        self.assertEqual(inner[80], 2)
        self.assertEqual(inner[96], 1)

if __name__ == "__main__":
    unittest.main()
