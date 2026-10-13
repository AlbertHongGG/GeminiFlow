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
