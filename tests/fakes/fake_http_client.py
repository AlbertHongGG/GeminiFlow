from typing import Dict, Any

class FakeHttpClient:
    def __init__(self):
        self.cookies: Dict[str, Any] = {}

    def update_cookies(self, cookies: Any):
        self.cookies = cookies

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
