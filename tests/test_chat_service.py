import unittest
from gemini_flow.application.chat_service import ChatService
from gemini_flow.domain.entities import ChatRequest, ImagePayload, SessionData
from gemini_flow.domain.exceptions import TokenExpiredError
from tests.fakes import (
    FakeAuthService,
    FakeSessionStore,
    FakeImageDownloader,
    FakeChatProvider,
    FakeHttpClient,
)

class TestChatService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.auth_service = FakeAuthService()
        self.session_store = FakeSessionStore()
        self.http_client = FakeHttpClient()
        self.image_downloader = FakeImageDownloader()

    def tearDown(self):
        self.image_downloader.cleanup()

    def _create_service(self, provider: FakeChatProvider) -> ChatService:
        return ChatService(
            auth_service=self.auth_service,
            chat_provider=provider,
            session_store=self.session_store,
            http_client=self.http_client,
            image_downloader=self.image_downloader,
        )

    async def test_text_to_text_generation(self):
        """Scenario 1: 文字生成文字 (Text-to-Text)"""
        provider = FakeChatProvider(mode="text")
        service = self._create_service(provider)

        req = ChatRequest(prompt="你好，請介紹你自己", session_id="session_abc")
        received_texts = []
        async for chunk in service.stream_chat(req):
            if chunk.text:
                received_texts.append(chunk.text)

        full_reply = "".join(received_texts)
        self.assertIn("哈囉！這是測試的第一段回答。", full_reply)
        self.assertIn("這是接續的第二段文字，回答完成！", full_reply)

        # Verify session state was automatically persisted and advanced
        saved_session = self.session_store.load("session_abc")
        self.assertIsNotNone(saved_session)
        self.assertEqual(saved_session.conversation_id, "c_fake_conv_123")
        self.assertEqual(saved_session.continuation_token, "AwAAAAAAAAAQANM7mFakeToken12345")
        self.assertEqual(saved_session.turn_index, 1)

    async def test_text_to_text_multi_turn(self):
        """Scenario 1b: 多輪對話延續 (Multi-turn Text-to-Text)"""
        provider = FakeChatProvider(mode="text")
        service = self._create_service(provider)

        # Prepopulate session store with turn 1
        self.session_store.save(SessionData(
            session_id="multi_turn_1",
            conversation_id="c_old",
            continuation_token="token_old",
            turn_index=1,
        ))

        req = ChatRequest(prompt="接續上一句", session_id="multi_turn_1")
        chunks = [c async for c in service.stream_chat(req)]
        self.assertTrue(len(chunks) > 0)

        # Verify captured session data in provider had turn 1
        captured_session = provider.captured_session_data[0]
        self.assertIsNotNone(captured_session)
        self.assertEqual(captured_session.conversation_id, "c_old")
        self.assertEqual(captured_session.turn_index, 1)

        # Verify that after turn 2 finishes, turn_index is advanced to 2
        saved_session = self.session_store.load("multi_turn_1")
        self.assertEqual(saved_session.turn_index, 2)

    async def test_text_to_image_generation(self):
        """Scenario 2: 文字生成圖片 (Text-to-Image)"""
        provider = FakeChatProvider(mode="image_gen")
        service = self._create_service(provider)

        req = ChatRequest(prompt="請幫我畫一隻貓咪")
        local_image_paths = []
        image_urls = []
        async for chunk in service.stream_chat(req):
            if chunk.image_url:
                image_urls.append(chunk.image_url)
            if chunk.image_local_path:
                local_image_paths.append(chunk.image_local_path)

        # Verify image was downloaded and local path was set
        self.assertEqual(len(image_urls), 1)
        self.assertEqual(len(local_image_paths), 1)
        self.assertTrue(local_image_paths[0].endswith("mock_generated_image.png"))
        self.assertEqual(len(self.image_downloader.downloaded_urls), 1)

    async def test_image_to_text_multimodal(self):
        """Scenario 3: 圖片生成文字 (Image-to-Text / Multimodal)"""
        provider = FakeChatProvider(mode="multimodal")
        service = self._create_service(provider)

        images = [
            ImagePayload(data=b"\x89PNGfake1", filename="menu1.png"),
            ImagePayload(data=b"\x89PNGfake2", filename="menu2.png"),
        ]
        req = ChatRequest(prompt="這兩張菜單有何不同？", images=images)

        text_output = []
        async for chunk in service.stream_chat(req):
            if chunk.text:
                text_output.append(chunk.text)

        full_text = "".join(text_output)
        self.assertIn("我已成功接收並分析您上傳的 2 張圖片", full_text)
        self.assertEqual(len(provider.captured_requests[0].images), 2)

    async def test_token_expiration_auto_retry(self):
        """Scenario 4: Token 過期自動重試機制"""
        provider = FakeChatProvider(mode="text", token_expired_once=True)
        service = self._create_service(provider)

        req = ChatRequest(prompt="測試過期重試", auto_refresh_cookies=True)
        chunks = [c async for c in service.stream_chat(req)]
        self.assertTrue(len(chunks) > 0)
        # ensure_valid_tokens called twice (initial + refresh on expiration)
        self.assertEqual(self.auth_service.call_count, 2)

    async def test_token_expiration_no_retry(self):
        """Scenario 5: 禁用自動重試時正確拋出 TokenExpiredError"""
        provider = FakeChatProvider(mode="text", token_expired_once=True)
        service = self._create_service(provider)

        req = ChatRequest(prompt="測試不重試", auto_refresh_cookies=False)
        with self.assertRaises(TokenExpiredError):
            async for _ in service.stream_chat(req):
                pass

if __name__ == "__main__":
    unittest.main()
