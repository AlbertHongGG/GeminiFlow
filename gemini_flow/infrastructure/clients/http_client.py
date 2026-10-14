from __future__ import annotations
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from curl_cffi.requests import AsyncSession, Response
from curl_cffi.requests.exceptions import RequestException, Timeout, CurlError

from gemini_flow.config import DEFAULT_HTTP_HEADERS
from gemini_flow.domain.interfaces import IHttpClient, IHttpResponse
from gemini_flow.domain.exceptions import NetworkError, TokenExpiredError, RateLimitError

logger = logging.getLogger("gemini_flow.http_client")

class CurlHttpResponse(IHttpResponse):
    """
    Lightweight, typed wrapper around curl_cffi Response implementing IHttpResponse.
    Supports await resp.text() for async caller compatibility.
    """
    def __init__(self, response: Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)

    @property
    def content(self) -> bytes:
        return self._response.content

    async def text(self) -> str:
        return self._response.text


class HttpClient(IHttpClient):
    """
    HTTP/2 and Chrome TLS impersonating HTTP client built on curl_cffi.
    Eliminates anti-bot rate-limiting and tarpit delays by emulating real Chrome fingerprints.
    """
    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        proxy: Optional[str] = None,
        impersonate: str = "chrome120",
        timeout: Optional[float] = 120.0,
    ):
        merged_headers = dict(DEFAULT_HTTP_HEADERS)
        if headers:
            merged_headers.update(headers)
        self.default_headers = merged_headers
        self.default_cookies = cookies or {}
        self.proxy = proxy
        self.impersonate = impersonate
        self.timeout = timeout
        self._session: Optional[AsyncSession] = None

    async def __aenter__(self) -> HttpClient:
        self._session = AsyncSession(
            impersonate=self.impersonate,
            headers=self.default_headers,
            proxy=self.proxy,
            timeout=self.timeout,
        )
        if self.default_cookies:
            self.update_cookies(self.default_cookies)
        logger.debug(f"HttpClient (curl_cffi) session opened with impersonate={self.impersonate}, timeout={self.timeout}.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("HttpClient session closed.")

    def _get_session(self) -> AsyncSession:
        if not self._session:
            raise RuntimeError("HttpClient is not within an async context manager. Use 'async with HttpClient():'")
        return self._session

    def update_cookies(self, cookies: Dict[str, str]) -> None:
        session = self._get_session()
        for name, value in cookies.items():
            session.cookies.set(name, value, domain=".google.com")

    def _prepare_headers(self, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
        req_headers = dict(self.default_headers)
        if headers:
            req_headers.update(headers)
        return req_headers

    def _check_status(self, status_code: int, url: str, body_snippet: str = "") -> None:
        if status_code == 429:
            logger.warning(f"Rate limited (HTTP 429) on {url}")
            raise RateLimitError(f"HTTP 429 Too Many Requests: Rate limited by Google on {url}")
        if status_code in (401, 403):
            logger.warning(f"Authentication rejected (HTTP {status_code}) on {url}")
            raise TokenExpiredError(f"Token expired or unauthorized: HTTP {status_code} body={body_snippet[:120]}")
        if status_code >= 400:
            logger.error(f"HTTP error {status_code} on {url}: {body_snippet[:200]}")
            raise NetworkError(f"Request to {url} failed: HTTP {status_code} body={body_snippet[:300]}")

    async def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        logger.debug(f"GET {url}")
        req_headers = self._prepare_headers(headers)
        try:
            resp = await self._get_session().get(url, headers=req_headers, proxy=self.proxy, timeout=self.timeout)
            self._check_status(resp.status_code, url, resp.text)
            return resp.text
        except (RequestException, Timeout, CurlError) as e:
            logger.error(f"GET {url} failed: {e}")
            raise NetworkError(f"Network request failed: {e}") from e

    async def post_stream(
        self,
        url: str,
        params: Dict[str, str],
        data: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncGenerator[str, None]:
        logger.debug(f"POST STREAM {url}")
        req_headers = self._prepare_headers(headers)
        try:
            resp = await self._get_session().post(
                url,
                params=params,
                data=data,
                headers=req_headers,
                stream=True,
                proxy=self.proxy,
                timeout=self.timeout,
            )
            self._check_status(resp.status_code, url)
            async for chunk in resp.aiter_lines():
                line = chunk.decode("utf-8", errors="ignore").rstrip("\r\n")
                if line:
                    yield line + "\n"
        except (RequestException, Timeout, CurlError) as e:
            logger.error(f"POST STREAM {url} failed: {e}")
            raise NetworkError(f"Network streaming request failed: {e}") from e

    async def post_form(
        self,
        url: str,
        data: Any,
        headers: Optional[Dict[str, str]] = None,
    ) -> IHttpResponse:
        logger.debug(f"POST FORM {url}")
        req_headers = self._prepare_headers(headers)
        try:
            resp = await self._get_session().post(url, data=data, headers=req_headers, proxy=self.proxy, timeout=self.timeout)
            self._check_status(resp.status_code, url, resp.text)
            return CurlHttpResponse(resp)
        except (RequestException, Timeout, CurlError) as e:
            logger.error(f"POST FORM {url} failed: {e}")
            raise NetworkError(f"Network form request failed: {e}") from e
