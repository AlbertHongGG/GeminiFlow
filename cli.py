import argparse
import asyncio
import sys
from pathlib import Path

# Allow running without installation
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gemini_flow.models import ChatRequest, ImagePayload
from gemini_flow.services.gemini_client import GeminiClient

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gemini_flow", description="Gemini web(cookie) client")
    sub = p.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="Send a prompt and stream text output")
    chat.add_argument("prompt", help="User prompt")
    chat.add_argument("-m", "--model", default="gemini-3-pro")
    chat.add_argument("-c", "--cookies-dir", type=Path, required=True)
    chat.add_argument(
        "--image",
        action="append",
        type=Path,
        default=None,
        help="Attach a local image (repeatable). Example: --image ./photo.png",
    )
    chat.add_argument("--lang", default="zh-TW")
    chat.add_argument("--proxy", default=None)
    chat.add_argument("--debug", action="store_true", help="Print debug diagnostics")
    chat.add_argument("--session-id", default=None, help="Maintain chat history with this session ID")
    chat.add_argument("--system-prompt", default=None, help="System prompt to set context/behavior")

    return p

async def _run_chat(args: argparse.Namespace) -> int:
    try:
        images = []
        if args.image:
            for p in args.image:
                data = p.read_bytes()
                images.append(ImagePayload(data=data, filename=p.name))
        
        req = ChatRequest(
            prompt=args.prompt,
            model=args.model,
            language=args.lang,
            images=images,
            session_id=args.session_id,
            proxy=args.proxy,
            debug=args.debug
        )
        
        from gemini_flow.infra.ai_logger import AILogger
        logger = AILogger()
        
        client = GeminiClient(cookies_dir=args.cookies_dir)
        
        had_output = False
        full_text = []
        response_images = []
        
        async for chunk in client.stream_chat(req):
            if chunk.text:
                had_output = True
                full_text.append(chunk.text)
                print(chunk.text, end="", flush=True)
            if chunk.image_saved_path:
                response_images.append(chunk.image_saved_path)
                print(f"\n[Image saved to: {chunk.image_saved_path}]")
            elif chunk.image_url:
                response_images.append(chunk.image_url)
                print(f"\n[Image URL: {chunk.image_url}]")
        print()
        
        # Log the complete interaction
        logger.log_interaction(req, "".join(full_text), response_images)
        
        if args.debug and not had_output:
            print("[debug] No text chunks were output.")
        return 0
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

def main() -> None:
    args = _build_parser().parse_args()
    if args.cmd == "chat":
        raise SystemExit(asyncio.run(_run_chat(args)))
    raise SystemExit(2)

if __name__ == "__main__":
    main()
