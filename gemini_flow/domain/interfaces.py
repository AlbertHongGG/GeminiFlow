import abc
from typing import AsyncGenerator, List, Optional, Any
from pathlib import Path
from .entities import ChatRequest, ChatResponseChunk, SessionData, GeminiTokens

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
