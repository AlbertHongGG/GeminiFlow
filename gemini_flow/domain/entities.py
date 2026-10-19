from __future__ import annotations
import time
from typing import Optional, List, Union, Dict
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
    def is_continuation(self) -> bool:
        return bool(self.turn_index > 0 and self.conversation_id and self.continuation_token)

    @property
    def is_new(self) -> bool:
        return not self.is_continuation

    def advance_turn(self, continuation_token: Optional[str] = None) -> None:
        if continuation_token:
            self.continuation_token = continuation_token
            self.turn_index += 1
        self.updated_at = time.time()


class ChatResponseChunk(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    conversation_id: Optional[str] = None
    continuation_token: Optional[str] = None


class GeminiCredentials(BaseModel):
    cookies: Dict[str, str] = Field(default_factory=dict)
    server_bl: Optional[str] = None
    api_key: str = "AIzaSyAPW83vB9zFQqfpMup_cMJdELqDQkWvTho"
    sid: Optional[str] = None
    snlm0e: Optional[str] = None

    @property
    def sapisid(self) -> Optional[str]:
        return self.cookies.get("SAPISID") or self.cookies.get("__Secure-3PAPISID") or self.cookies.get("__Secure-1PAPISID")


import uuid


class UploadedImageAttachment(BaseModel):
    ref_url: str
    filename: str
    mime_type: str = "image/jpeg"
    attachment_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))


class BotguardToken(BaseModel):
    token: str
    salt: str
    created_at: float = Field(default_factory=time.time)

