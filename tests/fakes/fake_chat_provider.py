from typing import AsyncGenerator, Optional, List
from gemini_flow.domain.interfaces import IChatProvider
from gemini_flow.domain.entities import ChatRequest, ChatResponseChunk, SessionData, GeminiCredentials
from gemini_flow.domain.exceptions import TokenExpiredError

class FakeChatProvider(IChatProvider):
    def __init__(
        self,
        mode: str = "text",
        token_expired_once: bool = False,
        custom_chunks: Optional[List[ChatResponseChunk]] = None,
    ):
        self.mode = mode
        self.token_expired_once = token_expired_once
        self.expired_occurred = False
        self.custom_chunks = custom_chunks
        self.captured_requests: List[ChatRequest] = []
        self.captured_session_data: List[Optional[SessionData]] = []

    async def stream_generate(
        self,
        request: ChatRequest,
        credentials: GeminiCredentials,
        session_data: Optional[SessionData] = None,
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        self.captured_requests.append(request)
        self.captured_session_data.append(session_data.model_copy() if session_data else None)

        if self.token_expired_once and not self.expired_occurred:
            self.expired_occurred = True
            raise TokenExpiredError("Token expired during stream_generate")

        if self.custom_chunks is not None:
            for chunk in self.custom_chunks:
                yield chunk
            return

        # 1. Emit Session / Context first
        yield ChatResponseChunk(
            conversation_id="c_fake_conv_123",
            continuation_token="AwAAAAAAAAAQANM7mFakeToken12345",
        )

        if self.mode == "text":
            # Text generation simulation
            yield ChatResponseChunk(text="哈囉！這是測試的第一段回答。")
            yield ChatResponseChunk(text="這是接續的第二段文字，回答完成！")

        elif self.mode == "image_gen":
            # Image generation simulation
            yield ChatResponseChunk(text="正在為您繪製圖片...")
            yield ChatResponseChunk(
                image_url="https://lh3.googleusercontent.com/gg-dl/mock_image_id_xyz=s0-d"
            )

        elif self.mode == "multimodal":
            # Multimodal image analysis simulation
            num_imgs = len(request.images)
            yield ChatResponseChunk(text=f"我已成功接收並分析您上傳的 {num_imgs} 張圖片。這是一張測試圖片。")

        else:
            yield ChatResponseChunk(text="預設回應")
