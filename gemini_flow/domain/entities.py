from typing import Optional, List
from pydantic import BaseModel, Field

class ImagePayload(BaseModel):
    data: bytes
    filename: str

class ChatRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    model: str = "gemini-3-pro"
    language: str = "zh-TW"
    images: List[ImagePayload] = Field(default_factory=list)
    session_id: Optional[str] = None
    auto_refresh_cookies: bool = True

class SessionData(BaseModel):
    session_id: str
    conversation_ids: List[str] = Field(default_factory=list)

class ChatResponseChunk(BaseModel):
    text: Optional[str] = None
    image_url: Optional[str] = None
    image_local_path: Optional[str] = None
    session_ids: Optional[List[str]] = None

class GeminiTokens(BaseModel):
    snlm0e: str
    sid: Optional[str] = None
