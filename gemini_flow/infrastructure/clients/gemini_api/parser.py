from __future__ import annotations
from .webchannel_parser import WebChannelStreamParser, ParsedStreamDelta

class StreamParser(WebChannelStreamParser):
    """
    Stream parser implementation for Gemini streaming chunks.
    Aliases to WebChannelStreamParser.
    """
    pass

__all__ = ["StreamParser", "WebChannelStreamParser", "ParsedStreamDelta"]
