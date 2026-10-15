import argparse
from pathlib import Path


def create_parser() -> argparse.ArgumentParser:
    """Builds and configures the top-level CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="gemini_flow",
        description="Gemini Flow CLI Client - High performance reverse-engineered Gemini client",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="Send a prompt and stream text output")
    
    # Prompt arguments: supports either positional inline text or file (-f / --file)
    chat.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="User prompt text (optional if -f/--file is provided)",
    )
    chat.add_argument(
        "-f",
        "--file",
        type=Path,
        default=None,
        help="Path to a text file to use as the prompt",
    )
    
    # Model & Generation parameters
    chat.add_argument(
        "-m",
        "--model",
        default="gemini-3.8-flash",
        help="Model name (e.g. gemini-3.8-flash, gemini-3-pro)",
    )
    chat.add_argument(
        "-t",
        "--thinking",
        choices=["low", "medium", "high"],
        default="low",
        help="Thinking mode level (low, medium, high), default: low",
    )
    chat.add_argument(
        "--image",
        action="append",
        type=Path,
        default=None,
        help="Attach a local image (repeatable). Example: --image ./photo.png",
    )
    chat.add_argument(
        "--lang",
        default="zh-TW",
        help="Preferred response language (default: zh-TW)",
    )
    chat.add_argument(
        "--session-id",
        default=None,
        help="Maintain chat history with this session ID",
    )
    
    # System prompt arguments: inline text or file
    chat.add_argument(
        "--system-prompt",
        default=None,
        help="System prompt to set context/behavior",
    )
    chat.add_argument(
        "--system-prompt-file",
        type=Path,
        default=None,
        help="Path to a text file to use as the system prompt",
    )

    # Config arguments
    chat.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    return parser
