import unittest
import time
from unittest.mock import AsyncMock, patch
from gemini_flow.domain.exceptions import VmExecutionError, ChallengeFetchError
from gemini_flow.infrastructure.attestation.waa_client import WaaClient
from gemini_flow.infrastructure.attestation.v8_runtime import BotguardV8Runtime
from gemini_flow.infrastructure.attestation.v8_signer import EmbeddedV8TokenSigner

class TestAttestation(unittest.IsolatedAsyncioTestCase):
    def test_waa_client_cache_validity(self):
        client = WaaClient(cache_ttl_seconds=10.0)
        self.assertFalse(client.is_cache_valid)

        client._cached_bytecode = "BYTECODE_ABC"
        client._cached_script_code = "console.log(1);"
        client._cached_at = time.time()
        self.assertTrue(client.is_cache_valid)

        # Expired cache
        client._cached_at = time.time() - 20.0
        self.assertFalse(client.is_cache_valid)

    def test_v8_runtime_execution_error_on_invalid_script(self):
        with self.assertRaises(VmExecutionError):
            BotguardV8Runtime("invalid syntax {{{", "bytecode")

    async def test_embedded_v8_signer_pipeline(self):
        # Create a mock WaaClient returning a mock botguard script
        mock_waa = AsyncMock(spec=WaaClient)
        mock_script = """
        window.botguard = {
            bg: function(bytecode) {
                return {
                    invoke: function(cb, asyncFlag, qhObj) {
                        var qh = (qhObj && qhObj[0] && qhObj[0].qh) || "no_qh";
                        return "!MOCK_TOKEN_" + qh.substring(0, 8);
                    }
                };
            }
        };
        """
        mock_waa.get_challenge.return_value = ("mock_bytecode", mock_script)

        signer = EmbeddedV8TokenSigner(waa_client=mock_waa)
        bg_token = await signer.sign("測試 Prompt", conversation_id="c_12345")

        self.assertTrue(bg_token.token.startswith("!MOCK_TOKEN_"))
        self.assertEqual(len(bg_token.salt), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in bg_token.salt))
        signer.close()

    def test_waa_client_proxy_configuration(self):
        client = WaaClient(proxy="http://user:pass@127.0.0.1:8080", timeout=25.0)
        self.assertEqual(client._proxy, "http://user:pass@127.0.0.1:8080")
        self.assertEqual(client._timeout, 25.0)

    def test_v8_signer_proxy_propagation(self):
        signer = EmbeddedV8TokenSigner(proxy="http://127.0.0.1:1080")
        self.assertEqual(signer._waa_client._proxy, "http://127.0.0.1:1080")
        signer.close()

    def test_v8_runtime_special_characters_escaping(self):
        # Verify that conversation_id with quotes, backslashes, and newlines doesn't break JS syntax
        mock_script = """
        window.botguard = {
            bg: function(bytecode) {
                return {
                    invoke: function(cb, asyncFlag, qhObj) {
                        return "!TOKEN_OK";
                    }
                };
            }
        };
        """
        runtime = BotguardV8Runtime(mock_script, "mock_bc")
        special_cid = 'conv_"hello"\\world\nwith\'special\'chars'
        token = runtime.generate_token(query_hash="abc123hash", conversation_id=special_cid)
        self.assertEqual(token, "!TOKEN_OK")
        runtime.close()
        self.assertIsNone(runtime._mr)

if __name__ == "__main__":
    unittest.main()
