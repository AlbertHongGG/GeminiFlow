import asyncio
import sys
import base64
from pathlib import Path
import uuid

# Import our brand new SDK!
from gemini_flow.sdk import GeminiFlowClient

def get_image_base64(filepath: str) -> str:
    path = Path(filepath)
    if not path.exists():
        print(f"⚠️ 警告：找不到測試圖片 {filepath}，這將導致圖片測試失敗。")
        return ""
    mime_type = "image/png"
    if path.suffix.lower() in [".jpg", ".jpeg"]:
        mime_type = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime_type = "image/webp"
        
    encoded = base64.b64encode(path.read_bytes()).decode('utf-8')
    return f"data:{mime_type};base64,{encoded}"

async def test_health(client: GeminiFlowClient):
    print("--------------------------------------------------")
    print("Testing health endpoint using SDK...")
    try:
        data = await client.health()
        print(f"✅ Health check passed: {data}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")

async def test_chat_text(client: GeminiFlowClient):
    print("--------------------------------------------------")
    print("Testing chat endpoint (Text Only) using SDK...")
    try:
        response = await client.chat(
            prompt="請詳細解釋量子力學中的『薛丁格的貓』思維實驗，並試著舉出一個日常生活中相似的情境來做比喻。請盡量寫得生動且易於理解，字數大約 300 字左右。"
        )
        print(f"✅ /chat text response:\n{response.get('text', '')}")
    except Exception as e:
        print(f"❌ /chat text failed: {e}")

async def test_stream_text(client: GeminiFlowClient):
    print("--------------------------------------------------")
    print("Testing stream endpoint (Text Only) using SDK...")
    print("Streaming output:\n", end="", flush=True)
    try:
        stream_gen = client.stream(
            prompt="請寫一篇關於『未來 2050 年的人工智慧將如何改變人類生活』的短文。請分成食、衣、住、行四個方面進行詳細探討，並加上結論。要求內容豐富且具有想像力。"
        )
        async for data in stream_gen:
            if "chunk" in data:
                print(data["chunk"], end="", flush=True)
            elif "path" in data or "url" in data:
                print(f"\n[Image output in stream: {data}]")
        print("\n\n✅ /stream text test finished.")
    except Exception as e:
        print(f"\n❌ Exception during /stream: {e}")

async def test_chat_image_description(client: GeminiFlowClient, image_b64: str):
    print("--------------------------------------------------")
    print("Testing chat endpoint (Image Description) using SDK...")
    if not image_b64:
        print("❌ 跳過圖片測試，因為找不到圖片。")
        return
        
    try:
        response = await client.chat(
            prompt="這是一張照片。請詳細描述這張照片裡的男人，包含他的外貌特徵、穿著打扮、臉部表情，以及他身處的背景環境。請盡可能地描述細節。",
            images=[image_b64]
        )
        print(f"✅ /chat image description response:\n{response.get('text', '')}")
    except Exception as e:
        print(f"❌ /chat image description failed: {e}")

async def test_chat_image_generation(client: GeminiFlowClient, image_b64: str):
    print("--------------------------------------------------")
    print("Testing chat endpoint (Image Generation / Modification) using SDK...")
    if not image_b64:
        print("❌ 跳過圖片生成測試，因為找不到圖片。")
        return
        
    try:
        response = await client.chat(
            prompt="幫照片上的男人戴上聖誕帽，請生成一張新的圖片給我。",
            images=[image_b64]
        )
        print(f"✅ /chat image generation response text:\n{response.get('text', '')}")
        images = response.get('images', [])
        if images:
            print(f"✅ Generated/Saved Images: {images}")
        else:
            print("⚠️ 沒有偵測到回傳或生成的圖片。請確認該模型是否支援圖片生成並回傳正確格式。")
    except Exception as e:
        print(f"❌ /chat image generation failed: {e}")

async def test_chat_session(client: GeminiFlowClient):
    print("--------------------------------------------------")
    print("Testing chat endpoint (Session Context Memory) using SDK...")
    session_id = f"test-session-{uuid.uuid4().hex[:8]}"
    print(f"Using Session ID: {session_id}")
    
    # 步驟一：提供資訊
    print("\n[Step 1] Providing information to the assistant...")
    try:
        response_1 = await client.chat(
            prompt="你好，我的名字叫做 Jason，我最喜歡的顏色是深海藍色。請記住這兩個資訊，並跟我打個招呼。",
            session_id=session_id
        )
        print(f"Assistant replied: {response_1.get('text', '')}")
    except Exception as e:
        print(f"❌ Step 1 failed: {e}")
        return
            
    await asyncio.sleep(1)
    
    # 步驟二：提問以驗證記憶
    print("\n[Step 2] Asking questions to verify memory...")
    try:
        response_2 = await client.chat(
            prompt="我們剛剛聊過天，請問你還記得我叫什麼名字嗎？還有我最喜歡的顏色是什麼？",
            session_id=session_id
        )
        reply = response_2.get('text', '')
        print(f"Assistant replied: {reply}")
        if "Jason" in reply and ("藍" in reply or "blue" in reply.lower()):
            print("✅ Session memory test passed! (Assistant successfully recalled the name and color)")
        else:
            print("⚠️ Session memory test might have failed. The expected keywords were not found in the response.")
    except Exception as e:
        print(f"❌ Step 2 failed: {e}")


async def main():
    if sys.stdout.encoding.lower() != 'utf-8':
        try: sys.stdout.reconfigure(encoding='utf-8')
        except Exception: pass
        
    print(f"Starting comprehensive server tests using GeminiFlow SDK\n")
    
    # Instantiate our SDK Client
    client = GeminiFlowClient(base_url="http://127.0.0.1:8000")
    
    input_image_path = Path(__file__).resolve().parent / "input" / "大為.png"
    image_b64 = get_image_base64(str(input_image_path))
    
    await test_health(client)
    await test_chat_text(client)
    await test_stream_text(client)
    # await test_chat_image_description(client, image_b64)
    # await test_chat_image_generation(client, image_b64)
    await test_chat_session(client)
        
    print("--------------------------------------------------")
    print("All SDK tests completed.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)
