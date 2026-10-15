import io
import sys
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from cli import main
from gemini_flow.application.chat_service import ChatService
from tests.fakes import (
    FakeAuthService,
    FakeSessionStore,
    FakeImageDownloader,
    FakeChatProvider,
    FakeHttpClient,
)

class TestCLI(unittest.TestCase):
    def setUp(self):
        self.auth_service = FakeAuthService()
        self.session_store = FakeSessionStore()
        self.http_client = FakeHttpClient()
        self.image_downloader = FakeImageDownloader()

    def tearDown(self):
        self.image_downloader.cleanup()

    def _build_service(self, mode: str) -> tuple[ChatService, FakeChatProvider]:
        provider = FakeChatProvider(mode=mode)
        service = ChatService(
            auth_service=self.auth_service,
            chat_provider=provider,
            session_store=self.session_store,
            http_client=self.http_client,
            image_downloader=self.image_downloader,
        )
        return service, provider

    def test_cli_text_to_text(self):
        """CLI: 文字生成文字"""
        service, provider = self._build_service("text")
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture
            code = main(["chat", "測試你好", "-m", "gemini-3.8-flash", "-t", "medium"], chat_service=service)
        finally:
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("哈囉！這是測試的第一段回答。", output)
        self.assertEqual(provider.captured_requests[0].prompt, "測試你好")
        self.assertEqual(provider.captured_requests[0].model_spec.thinking_level, 4)  # medium

    def test_cli_text_to_image(self):
        """CLI: 文字生成圖片"""
        service, _ = self._build_service("image_gen")
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout

        try:
            sys.stdout = stdout_capture
            code = main(["chat", "幫我畫一隻貓咪"], chat_service=service)
        finally:
            sys.stdout = old_stdout

        self.assertEqual(code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("[Image downloaded to:", output)

    def test_cli_image_to_text_multimodal(self):
        """CLI: 圖片生成文字 / 多模態圖片輸入"""
        service, provider = self._build_service("multimodal")

        with NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"\x89PNGmockimagebytes")
            tmp_path = Path(tmp.name)

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            code = main(["chat", "請描述這張照片", "--image", str(tmp_path)], chat_service=service)
        finally:
            sys.stdout = old_stdout
            tmp_path.unlink(missing_ok=True)

        self.assertEqual(code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("分析您上傳的 1 張圖片", output)
        self.assertEqual(len(provider.captured_requests[0].images), 1)

    def test_cli_prompt_from_file_short_flag(self):
        """CLI: 使用 -f 帶入檔案作為 prompt"""
        service, provider = self._build_service("text")
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("從檔案讀取的提示詞")
            tmp_path = Path(tmp.name)

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            code = main(["chat", "-f", str(tmp_path)], chat_service=service)
        finally:
            sys.stdout = old_stdout
            tmp_path.unlink(missing_ok=True)

        self.assertEqual(code, 0)
        self.assertEqual(provider.captured_requests[0].prompt, "從檔案讀取的提示詞")

    def test_cli_prompt_from_file_long_flag(self):
        """CLI: 使用 --file 帶入檔案作為 prompt"""
        service, provider = self._build_service("text")
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("長參數提示詞測試")
            tmp_path = Path(tmp.name)

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            code = main(["chat", "--file", str(tmp_path)], chat_service=service)
        finally:
            sys.stdout = old_stdout
            tmp_path.unlink(missing_ok=True)

        self.assertEqual(code, 0)
        self.assertEqual(provider.captured_requests[0].prompt, "長參數提示詞測試")

    def test_cli_system_prompt_from_file(self):
        """CLI: 使用 --system-prompt-file 帶入系統提示詞檔案"""
        service, provider = self._build_service("text")
        with NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write("你是一個專業的程式設計助理。")
            tmp_path = Path(tmp.name)

        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            code = main(["chat", "你好", "--system-prompt-file", str(tmp_path)], chat_service=service)
        finally:
            sys.stdout = old_stdout
            tmp_path.unlink(missing_ok=True)

        self.assertEqual(code, 0)
        self.assertEqual(provider.captured_requests[0].prompt, "你好")
        self.assertEqual(provider.captured_requests[0].system_prompt, "你是一個專業的程式設計助理。")

    def test_cli_conflict_prompt_and_file(self):
        """CLI: 同時傳入 prompt 與 -f 應報錯並回傳非 0"""
        service, _ = self._build_service("text")
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr

        try:
            sys.stderr = stderr_capture
            code = main(["chat", "行內提示詞", "-f", "dummy.txt"], chat_service=service)
        finally:
            sys.stderr = old_stderr

        self.assertEqual(code, 1)
        self.assertIn("Cannot specify both inline prompt and file source", stderr_capture.getvalue())

    def test_cli_no_prompt_provided(self):
        """CLI: 未提供 prompt 也未提供 -f 應報錯並回傳非 0"""
        service, _ = self._build_service("text")
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr

        try:
            sys.stderr = stderr_capture
            code = main(["chat"], chat_service=service)
        finally:
            sys.stderr = old_stderr

        self.assertEqual(code, 1)
        self.assertIn("No prompt provided", stderr_capture.getvalue())

    def test_cli_file_not_found(self):
        """CLI: 提供的 prompt 檔案不存在應回傳 1 並顯示友善錯誤"""
        service, _ = self._build_service("text")
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr

        try:
            sys.stderr = stderr_capture
            code = main(["chat", "-f", "non_existent_file_12345.txt"], chat_service=service)
        finally:
            sys.stderr = old_stderr

        self.assertEqual(code, 1)
        self.assertIn("not found", stderr_capture.getvalue())

    def test_cli_invalid_arguments(self):
        """CLI: 無效參數驗證與錯誤處理"""
        service, _ = self._build_service("text")
        stderr_capture = io.StringIO()
        old_stderr = sys.stderr

        try:
            sys.stderr = stderr_capture
            # Invalid thinking choice
            with self.assertRaises(SystemExit) as cm:
                main(["chat", "prompt", "--thinking", "super_high"], chat_service=service)
            self.assertEqual(cm.exception.code, 2)
        finally:
            sys.stderr = old_stderr

if __name__ == "__main__":
    unittest.main()
