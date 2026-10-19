import abc
from typing import AsyncGenerator, List, Optional, Any, Dict, Mapping
from pathlib import Path
from .entities import (
    ChatRequest,
    ChatResponseChunk,
    SessionData,
    GeminiCredentials,
    UploadedImageAttachment,
    BotguardToken,
    ImagePayload,
)

class IHttpResponse(abc.ABC):
    @property
    @abc.abstractmethod
    def status_code(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def headers(self) -> Mapping[str, str]:
        pass

    @abc.abstractmethod
    async def text(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def content(self) -> bytes:
        pass

class IHttpClient(abc.ABC):
    @abc.abstractmethod
    async def __aenter__(self) -> "IHttpClient":
        pass

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    @abc.abstractmethod
    def update_cookies(self, cookies: Dict[str, str]) -> None:
        pass

    @abc.abstractmethod
    async def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        pass

    @abc.abstractmethod
    def get_stream(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        pass

    @abc.abstractmethod
    async def post(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> IHttpResponse:
        pass

    @abc.abstractmethod
    async def post_form(
        self,
        url: str,
        data: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> IHttpResponse:
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        pass

class IAuthService(abc.ABC):
    @abc.abstractmethod
    async def ensure_valid_credentials(self) -> GeminiCredentials:
        pass
    
    @abc.abstractmethod
    async def get_cookies_dict(self) -> list[dict]:
        pass

class ITokenSigner(abc.ABC):
    @abc.abstractmethod
    async def sign(
        self, prompt: str, conversation_id: Optional[str] = None
    ) -> BotguardToken:
        pass

class IChatProvider(abc.ABC):
    @abc.abstractmethod
    async def stream_generate(
        self, 
        request: ChatRequest, 
        credentials: GeminiCredentials,
        session_data: Optional[SessionData] = None
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        pass

class ISessionStore(abc.ABC):
    @abc.abstractmethod
    def load(self, session_id: str) -> Optional[SessionData]:
        """Loads session data by ID."""
        pass

    @abc.abstractmethod
    def save(self, data: SessionData) -> None:
        """Saves session data."""
        pass

class IImageUploader(abc.ABC):
    @abc.abstractmethod
    async def upload_images(self, images: List[ImagePayload]) -> List[UploadedImageAttachment]:
        """
        Uploads images to the Gemini storage service.
        Returns a list of UploadedImageAttachment value objects.
        """
        pass

class IImageDownloader(abc.ABC):
    @abc.abstractmethod
    async def download_image(self, url: str, model_name: str) -> Path:
        """
        Downloads an image from the given URL and saves it locally.
        Returns the Path to the saved image.
        """
        pass

class IWebBrowser(abc.ABC):
    @abc.abstractmethod
    async def start(self) -> None:
        """Starts the browser provider and initializes resources."""
        pass
        
    @abc.abstractmethod
    async def stop(self) -> None:
        """Stops the browser provider and cleans up resources."""
        pass
        
    @abc.abstractmethod
    async def navigate_and_get_html(self, url: str, wait_selector: str, timeout: int = 5000) -> str:
        """Navigates to URL, waits for a selector, and returns HTML."""
        pass
        
    @abc.abstractmethod
    async def get_cookies(self) -> list[dict]:
        """Returns all browser cookies."""
        pass
        
    @abc.abstractmethod
    async def download_file(self, url: str, dest_path: Path) -> Path:
        """Downloads a file using the browser's context/cookies and saves it to dest_path."""
        pass
