import asyncio

from gemini_flow.services.gemini_client import GeminiClient
from gemini_flow.models import ChatRequest

async def main() -> None:
    client = GeminiClient()
    req = ChatRequest(
        prompt="講一個故事",
        model="gemini-3-pro",
    )

    async for chunk in client.stream_chat(req):
        if chunk.text:
            print(chunk.text, end="", flush=True)

if __name__ == "__main__":
    asyncio.run(main())