import time
from typing import Optional
from gemini_flow.domain.entities import BotguardToken
from gemini_flow.domain.interfaces import ITokenSigner

class FakeTokenSigner(ITokenSigner):
    """
    In-memory fake implementation of ITokenSigner for unit tests.
    Avoids external network calls to WAA and V8 runtime execution.
    """

    def __init__(self, token_prefix: str = "!FAKE_TOKEN_"):
        self.token_prefix = token_prefix
        self.sign_calls: list[tuple[str, Optional[str]]] = []

    async def sign(
        self, prompt: str, conversation_id: Optional[str] = None
    ) -> BotguardToken:
        self.sign_calls.append((prompt, conversation_id))
        fake_token = f"{self.token_prefix}{len(self.sign_calls)}"
        fake_salt = f"fake_salt_{len(self.sign_calls):032x}"[:32]
        return BotguardToken(
            token=fake_token,
            salt=fake_salt,
            created_at=time.time(),
        )
