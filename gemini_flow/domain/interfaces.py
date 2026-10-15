import abc
from typing import AsyncGenerator, List, Optional, Any, Dict
from pathlib import Path
from .entities import ChatRequest, ChatResponseChunk, SessionData, GeminiTokens, BotguardToken

class IHttpResponse(abc.ABC):
    @property
    @abc.abstractmethod
    def status_code(self) -> int:
        pass

    @property
    @abc.abstractmethod
    def headers(self) -> Dict[str, str]:
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
    async def post_stream(
        self,
        url: str,
        params: Dict[str, str],
        data: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
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
    async def ensure_valid_tokens(self) -> GeminiTokens:
        """
        Ensures that valid tokens (SNlM0e and sid) are available.
        This may involve launching a browser to refresh cookies and scraping the token.
        Raises exceptions (like RequireManualLoginError) if validation fails.
        """
        pass
    
    @abc.abstractmethod
    async def get_cookies_dict(self) -> list[dict]:
        """
        Returns the current stored cookies in a format suitable for the HTTP client.
        """
        pass

class ITokenSigner(abc.ABC):
    @abc.abstractmethod
    async def sign(
        self, prompt: str, conversation_id: Optional[str] = None
    ) -> BotguardToken:
        """
        Generates a cryptographic attestation token and salt for the given prompt and conversation.
        """
        pass

class IChatProvider(abc.ABC):
    @abc.abstractmethod
    async def stream_generate(
        self, 
        request: ChatRequest, 
        tokens: GeminiTokens,
        session_data: Optional[SessionData] = None
    ) -> AsyncGenerator[ChatResponseChunk, None]:
        """
        Streams a chat response from the provider given a request and valid tokens.
        May raise TokenExpiredError if the provider rejects the tokens during the request.
        """
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
