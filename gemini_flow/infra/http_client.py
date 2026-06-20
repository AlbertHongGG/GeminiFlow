import aiohttp
from typing import Optional, Dict, Any, AsyncGenerator
from ..exceptions import NetworkError

class HttpClient:
    def __init__(self, headers: Optional[Dict[str, str]] = None, cookies: Optional[Dict[str, str]] = None, proxy: Optional[str] = None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.proxy = proxy

    async def get_text(self, url: str) -> str:
        async with aiohttp.ClientSession(headers=self.headers, cookies=self.cookies) as session:
            try:
                async with session.get(url, proxy=self.proxy) as resp:
                    if resp.status >= 400:
                        raise NetworkError(f"GET {url} failed: HTTP {resp.status}")
                    return await resp.text()
            except aiohttp.ClientError as e:
                raise NetworkError(f"Network request failed: {e}") from e

    async def post_stream(self, url: str, params: Dict[str, str], data: Dict[str, str], headers: Optional[Dict[str, str]] = None) -> AsyncGenerator[str, None]:
        req_headers = {**self.headers, **(headers or {})}
        async with aiohttp.ClientSession(headers=req_headers, cookies=self.cookies) as session:
            try:
                async with session.post(url, params=params, data=data, proxy=self.proxy) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        raise NetworkError(f"POST {url} failed: HTTP {resp.status} body={body[:300]}")
                    
                    async for chunk in resp.content.iter_any():
                        yield chunk.decode("utf-8", errors="ignore")
            except aiohttp.ClientError as e:
                raise NetworkError(f"Network streaming request failed: {e}") from e
    
    async def post_json(self, url: str, json_data: Any, headers: Optional[Dict[str, str]] = None) -> Any:
        req_headers = {**self.headers, **(headers or {})}
        async with aiohttp.ClientSession(headers=req_headers, cookies=self.cookies) as session:
            try:
                async with session.post(url, json=json_data, proxy=self.proxy) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        raise NetworkError(f"POST {url} failed: HTTP {resp.status} body={body[:300]}")
                    return await resp.json()
            except aiohttp.ClientError as e:
                raise NetworkError(f"Network request failed: {e}") from e

    async def download_file(self, url: str) -> bytes:
        async with aiohttp.ClientSession(headers=self.headers, cookies=self.cookies) as session:
            try:
                async with session.get(url, proxy=self.proxy) as resp:
                    if resp.status >= 400:
                        raise NetworkError(f"Download {url} failed: HTTP {resp.status}")
                    return await resp.read()
            except aiohttp.ClientError as e:
                raise NetworkError(f"Network request failed: {e}") from e

    async def post_form(self, url: str, data: Any, headers: Optional[Dict[str, str]] = None) -> aiohttp.ClientResponse:
        req_headers = {**self.headers, **(headers or {})}
        async with aiohttp.ClientSession(headers=req_headers, cookies=self.cookies) as session:
            try:
                resp = await session.post(url, data=data, proxy=self.proxy)
                await resp.read()
                return resp
            except aiohttp.ClientError as e:
                raise NetworkError(f"Network form request failed: {e}") from e
