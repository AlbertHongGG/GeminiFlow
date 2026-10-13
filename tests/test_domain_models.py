import unittest
from gemini_flow.domain.models import ModelFamily, ThinkingLevel, ModelSpec
from gemini_flow.domain.entities import ChatRequest

class TestDomainModels(unittest.TestCase):
    def test_model_family(self):
        self.assertEqual(ModelFamily.FLASH.model_id, 1)
        self.assertEqual(ModelFamily.FLASH.model_hash, "56fdd199312815e2")
        self.assertEqual(ModelFamily.PRO.model_id, 3)
        self.assertEqual(ModelFamily.PRO.model_hash, "e6fa609c3fa255c0")

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

        # Test strict orthogonality: model name does NOT affect thinking level!
        spec_unspecified = ModelSpec.resolve("gemini-3.6-flash-thinking")
        self.assertEqual(spec_unspecified.family, ModelFamily.FLASH)
        self.assertEqual(spec_unspecified.thinking, ThinkingLevel.LOW)

        spec_explicit = ModelSpec.resolve("gemini-3.8-flash", thinking="high")
        self.assertEqual(spec_explicit.family, ModelFamily.FLASH)
        self.assertEqual(spec_explicit.thinking, ThinkingLevel.HIGH)

    def test_chat_request_integration(self):
        req = ChatRequest(prompt="Hello", model="gemini-3-pro", thinking="medium")
        self.assertEqual(req.model_spec.family, ModelFamily.PRO)
        self.assertEqual(req.model_spec.thinking, ThinkingLevel.MEDIUM)
        self.assertEqual(req.model_spec.model_id, 3)
        self.assertEqual(req.model_spec.thinking_level, 4)

if __name__ == "__main__":
    unittest.main()
