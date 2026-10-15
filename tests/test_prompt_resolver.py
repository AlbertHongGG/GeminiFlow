import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gemini_flow.cli.prompt_resolver import PromptResolver
from gemini_flow.domain.exceptions import (
    PromptConflictError,
    PromptEmptyError,
    PromptEncodingError,
    PromptFileNotFoundError,
    PromptInputError,
)


class TestPromptResolver(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = TemporaryDirectory()
        self.dir_path = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_resolve_inline_prompt(self):
        result = PromptResolver.resolve_prompt(inline_prompt="Hello Gemini")
        self.assertEqual(result, "Hello Gemini")

    def test_resolve_file_prompt(self):
        test_file = self.dir_path / "prompt.txt"
        test_file.write_text("Hello from file!\nLine 2", encoding="utf-8")

        result = PromptResolver.resolve_prompt(file_path=test_file)
        self.assertEqual(result, "Hello from file!\nLine 2")

    def test_resolve_file_with_utf8_bom(self):
        test_file = self.dir_path / "prompt_bom.txt"
        test_file.write_bytes(b"\xef\xbb\xbfPrompt with BOM")

        result = PromptResolver.resolve_prompt(file_path=test_file)
        self.assertEqual(result, "Prompt with BOM")

    def test_conflict_both_inline_and_file(self):
        test_file = self.dir_path / "prompt.txt"
        test_file.write_text("File prompt", encoding="utf-8")

        with self.assertRaises(PromptConflictError):
            PromptResolver.resolve_prompt(inline_prompt="Inline prompt", file_path=test_file)

    def test_missing_both_sources_raises_error(self):
        with self.assertRaises(PromptInputError):
            PromptResolver.resolve_prompt(inline_prompt=None, file_path=None)

    def test_file_not_found(self):
        non_existent = self.dir_path / "missing.txt"
        with self.assertRaises(PromptFileNotFoundError):
            PromptResolver.resolve_prompt(file_path=non_existent)

    def test_directory_passed_as_file(self):
        sub_dir = self.dir_path / "somedir"
        sub_dir.mkdir()
        with self.assertRaises(PromptFileNotFoundError):
            PromptResolver.resolve_prompt(file_path=sub_dir)

    def test_empty_file_raises_empty_error(self):
        empty_file = self.dir_path / "empty.txt"
        empty_file.write_text("   \n\t  ", encoding="utf-8")
        with self.assertRaises(PromptEmptyError):
            PromptResolver.resolve_prompt(file_path=empty_file)

    def test_empty_inline_raises_empty_error(self):
        with self.assertRaises(PromptEmptyError):
            PromptResolver.resolve_prompt(inline_prompt="   \n  ")

    def test_binary_file_raises_encoding_error(self):
        binary_file = self.dir_path / "image.png"
        binary_file.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\xff\xfe\xfd")
        with self.assertRaises(PromptEncodingError):
            PromptResolver.resolve_prompt(file_path=binary_file)

    def test_file_size_limit_exceeded(self):
        large_file = self.dir_path / "large.txt"
        large_file.write_bytes(b"A" * 100)

        with self.assertRaises(PromptInputError) as cm:
            PromptResolver.resolve_text(
                file_path=large_file,
                field_name="prompt",
                required=True,
                max_size_bytes=50,
            )
        self.assertIn("exceeds maximum allowed size", str(cm.exception))

    def test_optional_system_prompt_none_when_empty(self):
        result = PromptResolver.resolve_system_prompt(None, None)
        self.assertIsNone(result)

    def test_optional_system_prompt_resolved_from_file(self):
        test_file = self.dir_path / "sys.txt"
        test_file.write_text("You are an expert assistant.", encoding="utf-8")

        result = PromptResolver.resolve_system_prompt(file_path=test_file)
        self.assertEqual(result, "You are an expert assistant.")


if __name__ == "__main__":
    unittest.main()
