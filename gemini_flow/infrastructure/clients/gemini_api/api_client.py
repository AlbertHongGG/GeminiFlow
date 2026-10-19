from __future__ import annotations
from .webchannel_client import WebChannelChatProvider

class GeminiAPIClient(WebChannelChatProvider):
    """
    Modern Gemini API Client implementing Google's WebChannel protocol.
    Replaces deprecated StreamGenerate implementation.
    """
    pass

__all__ = ["GeminiAPIClient", "WebChannelChatProvider"]
