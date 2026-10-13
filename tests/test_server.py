import base64
import json
from aiohttp.test_utils import AioHTTPTestCase
from gemini_flow.application.chat_service import ChatService
from gemini_flow.domain.exceptions import AuthenticationError, NetworkError
from server import create_app
from tests.fakes import (
    FakeAuthService,
    FakeSessionStore,
    FakeImageDownloader,
    FakeChatProvider,
    FakeHttpClient,
)

class TestServerAPI(AioHTTPTestCase):
    def setUp(self):
        self.auth_service = FakeAuthService()
        self.session_store = FakeSessionStore()
        self.http_client = FakeHttpClient()
        self.image_downloader = FakeImageDownloader()
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.image_downloader.cleanup()

    def _build_chat_service(self, provider: FakeChatProvider) -> ChatService:
        return ChatService(
            auth_service=self.auth_service,
            chat_provider=provider,
            session_store=self.session_store,
            http_client=self.http_client,
            image_downloader=self.image_downloader,
        )

    async def get_application(self):
        self.chat_provider = FakeChatProvider(mode="text")
        self.chat_service = self._build_chat_service(self.chat_provider)
        return create_app(chat_service=self.chat_service)

    async def test_health_check(self):
        """GET /health"""
        resp = await self.client.request("GET", "/health")
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(data.get("ok"))

    async def test_chat_text_to_text(self):
        """POST /chat (文字生成文字)"""
        payload = {
            "prompt": "你好",
            "model": "gemini-3.8-flash",
            "thinking": "low",
        }
        resp = await self.client.request("POST", "/chat", json=payload)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("text", data)
        self.assertIn("哈囉！這是測試的第一段回答。", data["text"])
        self.assertEqual(data["images"], [])

    async def test_chat_text_to_image(self):
        """POST /chat (文字生成圖片)"""
        # Switch provider mode to image generation
        self.chat_provider.mode = "image_gen"

        payload = {"prompt": "生成一隻可愛的柴犬圖片"}
        resp = await self.client.request("POST", "/chat", json=payload)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertTrue(len(data["images"]) > 0)
        self.assertTrue(data["images"][0].endswith("/images/mock_generated_image.png"))

    async def test_chat_image_to_text_multimodal(self):
        """POST /chat (圖片生成文字 / 多模態分析)"""
        self.chat_provider.mode = "multimodal"

        # 1x1 transparent PNG in base64
        tiny_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        payload = {
            "prompt": "請描述這張圖片",
            "images": [tiny_b64],
        }
        resp = await self.client.request("POST", "/chat", json=payload)
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertIn("分析您上傳的 1 張圖片", data["text"])

    async def test_stream_sse_endpoint(self):
        """POST /stream (SSE 串流事件)"""
        self.chat_provider.mode = "text"
        payload = {"prompt": "串流測試"}
        resp = await self.client.request("POST", "/stream", json=payload)
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers.get("Content-Type"), "text/event-stream")

        content = await resp.text()
        self.assertIn("event: text", content)
        self.assertIn("event: done", content)

    async def test_invalid_json_request(self):
        """POST /chat 帶無效的 JSON 應回傳 400"""
        resp = await self.client.request("POST", "/chat", data="INVALID_JSON{", headers={"Content-Type": "application/json"})
        self.assertEqual(resp.status, 400)
        data = await resp.json()
        self.assertIn("error", data)

    async def test_missing_prompt_request(self):
        """POST /chat 缺少 prompt 應回傳 400"""
        resp = await self.client.request("POST", "/chat", json={"language": "zh-TW"})
        self.assertEqual(resp.status, 400)
        data = await resp.json()
        self.assertIn("error", data)
