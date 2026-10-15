import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from gemini_flow.application.chat_service import ChatService
from gemini_flow.cli import run_cli


def main(
    args_list: Optional[List[str]] = None,
    chat_service: Optional[ChatService] = None,
) -> int:
    """Entry point for the GeminiFlow CLI."""
    return run_cli(args_list=args_list, chat_service=chat_service)


if __name__ == "__main__":
    main()
