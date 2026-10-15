import json
import unittest
from gemini_flow.domain.entities import ChatRequest, GeminiTokens, SessionData
from gemini_flow.infrastructure.clients.gemini_api.api_client import GeminiAPIClient
from tests.fakes import FakeHttpClient, FakeTokenSigner
from tests.fixtures import SAMPLE_TEXT_LINE

class TestGeminiAPIClient(unittest.IsolatedAsyncioTestCase):
    async def test_stream_generate_with_botguard_signing(self):
        fake_http = FakeHttpClient(stream_chunks=[SAMPLE_TEXT_LINE + "\n"])
        fake_signer = FakeTokenSigner(token_prefix="!TEST_BG_TOKEN_")
        
        client = GeminiAPIClient(
            http_client=fake_http,
            server_bl="boq_gemini-web-uiserver_20261012.19_p1",
            token_signer=fake_signer,
        )

        session = SessionData(
            session_id="sess_test",
            conversation_id="c_test_123",
            continuation_token="token_test_abc",
            turn_index=1,
        )
        req = ChatRequest(
            prompt="哈囉，測試簽名",
            system_prompt="你是一個助手",
            model="gemini-3.8-flash",
            thinking="low",
        )
        tokens = GeminiTokens(snlm0e="TEST_SNLM0E", sid="987654321")

        chunks = []
        async for chunk in client.stream_generate(req, tokens, session_data=session):
            chunks.append(chunk)

        # 1. Verify token signer was invoked with effective prompt (including system prompt) and conversation_id
        self.assertEqual(len(fake_signer.sign_calls), 1)
        expected_effective_prompt = "System:\n你是一個助手\n\nUser:\n哈囉，測試簽名"
        self.assertEqual(fake_signer.sign_calls[0][0], expected_effective_prompt)
        self.assertEqual(fake_signer.sign_calls[0][1], "c_test_123")

        # 2. Verify HTTP request was sent with Botguard token in f.req
        self.assertEqual(len(fake_http.post_stream_calls), 1)
        call_url, call_params, call_data, call_headers = fake_http.post_stream_calls[0]
        
        f_req = json.loads(call_data["f.req"])
        inner = json.loads(f_req[1])
        
        self.assertEqual(inner[3], "!TEST_BG_TOKEN_1")
        self.assertTrue(inner[4].startswith("fake_salt_"))
        self.assertEqual(inner[71][0], "c_test_123")

        # 3. Verify chunks yielded
        text_chunks = [c.text for c in chunks if c.text]
        self.assertTrue(len(text_chunks) > 0)

    def test_api_client_proxy_propagation(self):
        fake_http = FakeHttpClient()
        fake_http.proxy = "http://proxy.test:8080"
        client = GeminiAPIClient(http_client=fake_http)
        self.assertEqual(client.token_signer._waa_client._proxy, "http://proxy.test:8080")
        client.token_signer.close()

if __name__ == "__main__":
    unittest.main()
