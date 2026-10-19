from collections.abc import Mapping
from typing import Dict, Any, Optional, AsyncGenerator
from gemini_flow.domain.interfaces import IHttpClient, IHttpResponse
from gemini_flow.infrastructure.clients.http_client import CaseInsensitiveDict

class FakeHttpResponse(IHttpResponse):
    def __init__(self, status_code: int = 200, headers: Optional[Mapping[str, str]] = None, content: bytes = b""):
        self._status_code = status_code
        self._headers = CaseInsensitiveDict(headers or {})
        self._content = content

    @property
    def status_code(self) -> int:
        return self._status_code

    @property
    def status(self) -> int:
        return self._status_code

    @property
    def headers(self) -> Mapping[str, str]:
        return self._headers

    @property
    def content(self) -> bytes:
        return self._content

    async def text(self) -> str:
        return self._content.decode("utf-8", errors="replace")


class FakeHttpClient(IHttpClient):
    def __init__(self, stream_chunks: Optional[list[str]] = None):
        self.cookies: Dict[str, Any] = {}
        self.response_text: str = ""
        self.stream_chunks: list[str] = stream_chunks or []
        self.post_stream_calls: list[tuple[str, Dict[str, str], Dict[str, str], Optional[Dict[str, str]]]] = []
        self.post_calls: list[tuple[str, Optional[Dict[str, str]], Any, Optional[Dict[str, str]]]] = []
        self.get_stream_calls: list[tuple[str, Optional[Dict[str, str]], Optional[Dict[str, str]]]] = []

    def update_cookies(self, cookies: Any) -> None:
        self.cookies = cookies

    async def __aenter__(self) -> "FakeHttpClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass

    async def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        return self.response_text

    async def get_stream(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        self.get_stream_calls.append((url, params, headers))
        for chunk in self.stream_chunks:
            yield chunk

    async def post(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        data: Any = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> IHttpResponse:
        self.post_calls.append((url, params, data, headers))
        headers_dict = {"x-http-session-id": "fake_gsessionid_123"}
        return FakeHttpResponse(200, headers_dict, b"fake_post_response")

    async def post_stream(
        self,
        url: str,
        params: Dict[str, str],
        data: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        self.post_stream_calls.append((url, params, data, headers))
        for chunk in self.stream_chunks:
            yield chunk

    async def post_form(
        self,
        url: str,
        data: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> IHttpResponse:
        return FakeHttpResponse(200, {}, b"fake_upload_ref")

    async def close(self) -> None:
        pass
