from __future__ import annotations
import time
from typing import Optional, List, Union
from pydantic import BaseModel, Field
from .models import ThinkingLevel, ModelSpec

class ImagePayload(BaseModel):
    data: bytes
    filename: str

class ChatRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    model: str = "gemini-3.8-flash"
    thinking: Union[ThinkingLevel, str, int] = ThinkingLevel.LOW
    language: str = "zh-TW"
    images: List[ImagePayload] = Field(default_factory=list)
    session_id: Optional[str] = None
    auto_refresh_cookies: bool = True

    @property
    def model_spec(self) -> ModelSpec:
        return ModelSpec.resolve(self.model, self.thinking)

    @property
    def effective_prompt(self) -> str:
        if self.system_prompt:
            return f"System:\n{self.system_prompt}\n\nUser:\n{self.prompt}"
        return self.prompt


class SessionData(BaseModel):
    session_id: str
    conversation_id: Optional[str] = None
    continuation_token: Optional[str] = None
    turn_index: int = 0
    updated_at: float = Field(default_factory=time.time)

    @property
    def is_new(self) -> bool:
        return self.turn_index == 0 or not self.conversation_id

    def advance_turn(self, continuation_token: Optional[str] = None) -> None:
        self.turn_index += 1
        if continuation_token:
            self.continuation_token = continuation_token
        self.updated_at = time.time()


class ChatResponseChunk(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    conversation_id: Optional[str] = None
    continuation_token: Optional[str] = None


class GeminiTokens(BaseModel):
    snlm0e: str
    sid: Optional[str] = None
    server_bl: Optional[str] = None


class BotguardToken(BaseModel):
    token: str
    salt: str
    created_at: float = Field(default_factory=time.time)

