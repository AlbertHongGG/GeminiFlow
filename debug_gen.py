import asyncio
from pathlib import Path
from gemini_flow.models import ChatRequest, ImagePayload
from gemini_flow.services.gemini_client import GeminiClient
import base64

def get_image_base64(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        return ""
    mime_type = "image/png"
    if path.suffix.lower() in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime_type = "image/webp"
    encoded = base64.b64encode(path.read_bytes()).decode('utf-8')
    return f"data:{mime_type};base64,{encoded}"

def decode_image(value: str) -> ImagePayload:
    header, b64 = value.split(",", 1)
    payload = "".join(b64.split())
    padding = (-len(payload)) % 4
    if padding: payload += "=" * padding
    data = base64.b64decode(payload, validate=False)
    return ImagePayload(data=data, filename="upload_1.png")

async def main():
    img_b64 = get_image_base64("input/大為.png")
    if not img_b64:
        print("Image not found")
        return
        
    req = ChatRequest(
        prompt="幫照片上的男人戴上聖誕帽，請生成一張新的圖片給我。",
        images=[decode_image(img_b64)],
        model="gemini-3-pro",
        language="zh-TW",
        save_images=False,
        debug=True
    )
    
    client = GeminiClient()
    
    print("Sending request...")
    try:
        async for chunk in client.stream_chat(req):
            if chunk.text:
                print(f"TEXT DELTA: {chunk.text}")
            if chunk.image_url:
                print(f"IMAGE URL: {chunk.image_url}")
            if chunk.image_saved_path:
                print(f"IMAGE SAVED: {chunk.image_saved_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
