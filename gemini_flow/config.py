from __future__ import annotations
from pathlib import Path

# URLs
GEMINI_BASE_URL = "https://gemini.google.com"
GEMINI_REQUEST_URL = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
UPLOAD_IMAGE_URL = "https://content-push.googleapis.com/upload/"

# Protocol constants
REQUEST_BL_PARAM = "boq_assistant-bard-web-server_20260618.10_p0"
REQUIRED_COOKIE_NAME = "__Secure-1PSID"
GOOGLE_COOKIE_DOMAIN = ".google.com"

# Default Paths
DEFAULT_COOKIES_DIR = Path("user_cookies")
DEFAULT_SESSIONS_DIR = Path("output/sessions")
DEFAULT_IMAGE_OUTPUT_DIR = Path("output/image")

# Headers
DEFAULT_HTTP_HEADERS = {
    "authority": "gemini.google.com",
    "origin": "https://gemini.google.com",
    "referer": "https://gemini.google.com/",
    "x-same-domain": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

UPLOAD_IMAGE_HEADERS = {
    "authority": "content-push.googleapis.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.7",
    "authorization": "Basic c2F2ZXM6cyNMdGhlNmxzd2F2b0RsN3J1d1U=",
    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
    "origin": "https://gemini.google.com",
    "push-id": "feeds/mcudyrk2a4khkz",
    "referer": "https://gemini.google.com/",
    "x-goog-upload-command": "start",
    "x-goog-upload-header-content-length": "",
    "x-goog-upload-protocol": "resumable",
    "x-tenant-id": "bard-storage",
}

# Model Settings
MODEL_HEADERS = {
    "gemini-3-pro": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4,5,6,8],null,null,2,null,null,3,1,"{ext_uuid}"]'
    },
    "gemini-3.5-flash": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"56fdd199312815e2",null,null,0,[4,5,6,8],null,null,2,null,null,1,1,"{ext_uuid}"]'
    },
    "gemini-3-pro-image-preview": {
        "x-goog-ext-525001261-jspb": '[1,null,null,null,"e6fa609c3fa255c0",null,null,0,[4,5,6,8],null,null,2,null,null,3,2,"{ext_uuid}"]'
    },
}

import os
from dataclasses import dataclass

@dataclass
class AppConfig:
    debug: bool = False
    cookies_dir: Path = DEFAULT_COOKIES_DIR
    sessions_dir: Path = DEFAULT_SESSIONS_DIR
    image_output_dir: Path = DEFAULT_IMAGE_OUTPUT_DIR
    proxy: str | None = None

    @classmethod
    def from_env(cls) -> AppConfig:
        return cls(
            debug=os.getenv("DEBUG", "false").lower() in ("true", "1", "yes", "t"),
            cookies_dir=Path(os.getenv("COOKIES_DIR", str(DEFAULT_COOKIES_DIR))),
            sessions_dir=Path(os.getenv("SESSIONS_DIR", str(DEFAULT_SESSIONS_DIR))),
            image_output_dir=Path(os.getenv("IMAGE_OUTPUT_DIR", str(DEFAULT_IMAGE_OUTPUT_DIR))),
            proxy=os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
        )
