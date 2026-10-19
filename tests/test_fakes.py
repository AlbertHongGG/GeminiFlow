import unittest
from gemini_flow.infrastructure.clients.gemini_api.webchannel_parser import WebChannelStreamParser
from gemini_flow.domain.entities import ChatRequest, GeminiCredentials, SessionData
from tests.fakes import FakeAuthService, FakeSessionStore, FakeImageDownloader, FakeChatProvider
from tests.fixtures import SAMPLE_TEXT_LINE, SAMPLE_IMAGE_LINE

class TestFakesAndFixtures(unittest.IsolatedAsyncioTestCase):
    async def test_fake_auth(self):
        auth = FakeAuthService(fail_first_times=1)
        with self.assertRaises(Exception):
            await auth.ensure_valid_credentials()
        creds = await auth.ensure_valid_credentials()
        self.assertEqual(creds.snlm0e, "FAKE_SNLM0E_TOKEN")
        cookies = await auth.get_cookies_dict()
        self.assertEqual(len(cookies), 1)

    async def test_fake_session_store(self):
        store = FakeSessionStore()
        self.assertIsNone(store.load("s1"))
        store.save(SessionData(session_id="s1", conversation_id="c1", continuation_token="t1", turn_index=2))
        saved = store.load("s1")
        self.assertIsNotNone(saved)
        self.assertEqual(saved.conversation_id, "c1")
        self.assertEqual(saved.continuation_token, "t1")
        self.assertEqual(saved.turn_index, 2)

    async def test_fake_image_downloader(self):
        dl = FakeImageDownloader()
        try:
            path = await dl.download_image("https://example.com/test.png", "gemini-3.8-flash")
            self.assertTrue(path.exists())
            self.assertIn("https://example.com/test.png", dl.downloaded_urls)
        finally:
            dl.cleanup()

    async def test_fake_chat_provider_modes(self):
        # Text mode
        p_text = FakeChatProvider(mode="text")
        req = ChatRequest(prompt="測試")
        creds = GeminiCredentials(snlm0e="tok")
        chunks = [c async for c in p_text.stream_generate(req, creds)]
        self.assertTrue(any(c.conversation_id for c in chunks))
        self.assertTrue(any(c.text for c in chunks))

        # Image generation mode
        p_img = FakeChatProvider(mode="image_gen")
        chunks_img = [c async for c in p_img.stream_generate(req, creds)]
        self.assertTrue(any(c.image_url for c in chunks_img))

    def test_parser_with_fixtures(self):
        parser = WebChannelStreamParser()
        delta, conv_id, token = parser.extract_text_delta(SAMPLE_TEXT_LINE)
        self.assertEqual(conv_id, "c_11d858511efb9729")
        self.assertEqual(token, "AwAAAAAAAAAQANM7mBjXKZS5cPttExo")
        self.assertIn("這是測試回答第一部分", delta)

        candidates = parser.extract_image_candidates(SAMPLE_IMAGE_LINE)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(parser.classify_image_url(candidates[0]), "output")

if __name__ == "__main__":
    unittest.main()
