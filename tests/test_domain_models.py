import unittest
from gemini_flow.domain.models import ModelFamily, ThinkingLevel, ModelSpec
from gemini_flow.domain.entities import ChatRequest, SessionData

class TestDomainModels(unittest.TestCase):
    def test_model_family(self):
        self.assertEqual(ModelFamily.FLASH.model_id, 1)
        self.assertEqual(ModelFamily.FLASH.model_hash, "56fdd199312815e2")
        self.assertEqual(ModelFamily.PRO.model_id, 3)
        self.assertEqual(ModelFamily.PRO.model_hash, "e6fa609c3fa255c0")
        self.assertEqual(ModelFamily.ARGON.model_id, 8)
        self.assertEqual(ModelFamily.ARGON.model_hash, "95a4c0abcba24364")

    def test_thinking_level(self):
        self.assertEqual(ThinkingLevel.from_value("low"), ThinkingLevel.LOW)
        self.assertEqual(ThinkingLevel.from_value("1"), ThinkingLevel.LOW)
        self.assertEqual(ThinkingLevel.from_value("medium"), ThinkingLevel.MEDIUM)
        self.assertEqual(ThinkingLevel.from_value("4"), ThinkingLevel.MEDIUM)
        self.assertEqual(ThinkingLevel.from_value("high"), ThinkingLevel.HIGH)
        self.assertEqual(ThinkingLevel.from_value("2"), ThinkingLevel.HIGH)
        self.assertEqual(ThinkingLevel.from_value(None), ThinkingLevel.LOW)

    def test_model_spec_resolve(self):
        # Default
        spec = ModelSpec.resolve()
        self.assertEqual(spec.family, ModelFamily.FLASH)
        self.assertEqual(spec.thinking, ThinkingLevel.LOW)
        self.assertEqual(spec.model_id, 1)
        self.assertEqual(spec.thinking_level, 1)

        # Gemini 3.8 Flash with medium thinking
        spec = ModelSpec.resolve("gemini-3.8-flash", thinking="medium")
        self.assertEqual(spec.family, ModelFamily.FLASH)
        self.assertEqual(spec.thinking, ThinkingLevel.MEDIUM)
        self.assertEqual(spec.thinking_level, 4)

        # Gemini 3 Pro with high thinking
        spec = ModelSpec.resolve("gemini-3-pro", thinking="high")
        self.assertEqual(spec.family, ModelFamily.PRO)
        self.assertEqual(spec.thinking, ThinkingLevel.HIGH)
        self.assertEqual(spec.model_id, 3)
        self.assertEqual(spec.thinking_level, 2)

        # Gemini 4 Argon with low/medium/high thinking
        spec_argon_low = ModelSpec.resolve("gemini4Argon", thinking="low")
        self.assertEqual(spec_argon_low.family, ModelFamily.ARGON)
        self.assertEqual(spec_argon_low.model_id, 8)
        self.assertEqual(spec_argon_low.model_hash, "95a4c0abcba24364")
        self.assertEqual(spec_argon_low.thinking_level, 1)

        spec_argon_med = ModelSpec.resolve("gemini-4-argon", thinking=4)
        self.assertEqual(spec_argon_med.family, ModelFamily.ARGON)
        self.assertEqual(spec_argon_med.model_id, 8)
        self.assertEqual(spec_argon_med.thinking_level, 4)

        spec_argon_high = ModelSpec.resolve("argon", thinking="high")
        self.assertEqual(spec_argon_high.family, ModelFamily.ARGON)
        self.assertEqual(spec_argon_high.model_id, 8)
        self.assertEqual(spec_argon_high.thinking_level, 2)

    def test_session_data_entity(self):
        s = SessionData(session_id="test_session")
        self.assertTrue(s.is_new)
        self.assertEqual(s.turn_index, 0)
        self.assertIsNone(s.conversation_id)

        s.conversation_id = "c_123"
        s.advance_turn("token_abc")
        self.assertFalse(s.is_new)
        self.assertEqual(s.turn_index, 1)
        self.assertEqual(s.continuation_token, "token_abc")

    def test_chat_request_integration(self):
        req = ChatRequest(prompt="Hello", model="gemini4Argon", thinking="medium")
        self.assertEqual(req.model_spec.family, ModelFamily.ARGON)
        self.assertEqual(req.model_spec.thinking, ThinkingLevel.MEDIUM)
        self.assertEqual(req.model_spec.model_id, 8)
        self.assertEqual(req.model_spec.thinking_level, 4)

if __name__ == "__main__":
    unittest.main()
