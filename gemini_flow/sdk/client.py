import aiohttp
import json
from typing import AsyncGenerator, Dict, Any, List, Optional

class GeminiFlowClient:
    """
    Client SDK for GeminiFlow API.
    Provides a simple interface to interact with the /health, /chat, and /stream endpoints.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    async def health(self) -> Dict[str, Any]:
        """Check server health."""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/health") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def chat(self, 
                   prompt: str, 
                   system_prompt: Optional[str] = None,
                   model: str = "gemini-3-pro", 
                   language: str = "zh-TW", 
                   images: Optional[List[str]] = None,
                   session_id: Optional[str] = None,
                   save_images: bool = True) -> Dict[str, Any]:
        """
        Send a chat request and get the complete response at once.
        images should be a list of base64 encoded strings if provided.
        """
        payload = {
            "prompt": prompt,
            "model": model,
            "language": language,
            "save_images": save_images
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if images:
            payload["images"] = images
        if session_id:
            payload["session_id"] = session_id
            
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/chat", json=payload) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    raise Exception(f"HTTP {resp.status}: {text}")
                resp.raise_for_status()
                return await resp.json()

    async def stream(self, 
                     prompt: str, 
                     system_prompt: Optional[str] = None,
                     model: str = "gemini-3-pro", 
                     language: str = "zh-TW", 
                     images: Optional[List[str]] = None,
                     session_id: Optional[str] = None,
                     save_images: bool = True) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat request and yield Server-Sent Events (SSE) as they stream in.
        Returns dictionaries that may contain 'chunk', 'path', or 'url' keys.
        """
        payload = {
            "prompt": prompt,
            "model": model,
            "language": language,
            "save_images": save_images
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt
        if images:
            payload["images"] = images
        if session_id:
            payload["session_id"] = session_id
            
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/stream", json=payload) as resp:
                resp.raise_for_status()
                
                async for line in resp.content:
                    line = line.decode('utf-8').strip()
                    if not line:
                        continue
                    if line.startswith("event:"):
                        continue
                    if line.startswith("data:"):
                        data_str = line.split(":", 1)[1].strip()
                        try:
                            data = json.loads(data_str)
                            yield data
                        except json.JSONDecodeError:
                            pass
