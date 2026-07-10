import aiohttp
import logging
from typing import Optional, Dict, Any, AsyncGenerator
from ..exceptions import NetworkError

logger = logging.getLogger("gemini_flow.http_client")

class HttpClient:
    """
    A reusable HTTP client managing a single aiohttp.ClientSession.
    Must be used as an async context manager:
    
    async with HttpClient(...) as client:
        await client.get_text(...)
    """
    def __init__(self, headers: Optional[Dict[str, str]] = None, cookies: Optional[Dict[str, str]] = None, proxy: Optional[str] = None):
        self.default_headers = headers or {}
        self.default_cookies = cookies or {}
        self.proxy = proxy
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            headers=self.default_headers,
            cookies=self.default_cookies
        )
        logger.debug("HttpClient session opened.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            self._session = None
            logger.debug("HttpClient session closed.")

    def _get_session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("HttpClient is not within an async context manager. Use 'async with HttpClient():'")
        return self._session

    def update_cookies(self, cookies: Dict[str, str]):
        self._get_session().cookie_jar.update_cookies(cookies)

    async def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        logger.debug(f"GET {url}")
        try:
            async with self._get_session().get(url, headers=headers, proxy=self.proxy) as resp:
                if resp.status >= 400:
                    raise NetworkError(f"GET {url} failed: HTTP {resp.status}")
                return await resp.text()
        except aiohttp.ClientError as e:
            logger.error(f"GET {url} failed: {e}")
            raise NetworkError(f"Network request failed: {e}") from e

    async def post_stream(self, url: str, params: Dict[str, str], data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> AsyncGenerator[str, None]:
        logger.debug(f"POST STREAM {url}")
        try:
            async with self._get_session().post(url, params=params, data=data, headers=headers, proxy=self.proxy) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise NetworkError(f"POST {url} failed: HTTP {resp.status} body={body[:300]}")
                
                async for chunk in resp.content.iter_any():
                    yield chunk.decode("utf-8", errors="ignore")
        except aiohttp.ClientError as e:
            logger.error(f"POST STREAM {url} failed: {e}")
            raise NetworkError(f"Network streaming request failed: {e}") from e
    
    async def post_json(self, url: str, json_data: Any, headers: Optional[Dict[str, str]] = None) -> Any:
        logger.debug(f"POST JSON {url}")
        try:
            async with self._get_session().post(url, json=json_data, headers=headers, proxy=self.proxy) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise NetworkError(f"POST {url} failed: HTTP {resp.status} body={body[:300]}")
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"POST JSON {url} failed: {e}")
            raise NetworkError(f"Network request failed: {e}") from e

    async def download_file(self, url: str) -> bytes:
        logger.debug(f"DOWNLOAD {url}")
        try:
            async with self._get_session().get(url, proxy=self.proxy) as resp:
                if resp.status >= 400:
                    raise NetworkError(f"Download {url} failed: HTTP {resp.status}")
                return await resp.read()
        except aiohttp.ClientError as e:
            logger.error(f"DOWNLOAD {url} failed: {e}")
            raise NetworkError(f"Network request failed: {e}") from e

    async def post_form(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None) -> aiohttp.ClientResponse:
        logger.debug(f"POST FORM {url}")
        try:
            resp = await self._get_session().post(url, data=data, headers=headers, proxy=self.proxy)
            await resp.read()
            if resp.status >= 400:
                body = await resp.text()
                raise NetworkError(f"POST {url} failed: HTTP {resp.status} body={body[:300]}")
            return resp
        except aiohttp.ClientError as e:
            logger.error(f"POST FORM {url} failed: {e}")
            raise NetworkError(f"Network form request failed: {e}") from e
