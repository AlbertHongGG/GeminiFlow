from typing import List, Dict
from gemini_flow.domain.interfaces import IAuthService
from gemini_flow.domain.entities import GeminiCredentials

class FakeAuthService(IAuthService):
    def __init__(self, credentials: GeminiCredentials = None, cookies: List[Dict] = None, fail_first_times: int = 0):
        self.credentials = credentials or GeminiCredentials(snlm0e="FAKE_SNLM0E_TOKEN", sid="FAKE_SID_12345")
        self.cookies = cookies or [{"name": "__Secure-1PSID", "value": "fake_cookie", "domain": ".google.com"}]
        self.fail_first_times = fail_first_times
        self.call_count = 0

    async def ensure_valid_credentials(self) -> GeminiCredentials:
        self.call_count += 1
        if self.call_count <= self.fail_first_times:
            from gemini_flow.domain.exceptions import AuthenticationError
            raise AuthenticationError("Simulated token validation error")
        return self.credentials

    async def get_cookies_dict(self) -> List[Dict]:
        return self.cookies
