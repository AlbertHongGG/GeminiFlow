import json
from pathlib import Path
from typing import Dict
from gemini_flow.domain.exceptions import AuthenticationError

Cookies = Dict[str, str]

def parse_exported_cookie_list(cookie_export: object) -> Dict[str, Cookies]:
    if not isinstance(cookie_export, list):
        return {}

    by_domain: Dict[str, Cookies] = {}
    for item in cookie_export:
        if not isinstance(item, dict):
            continue
        domain = item.get("domain")
        name = item.get("name")
        value = item.get("value")
        if not domain or not name or value is None:
            continue
        by_domain.setdefault(str(domain), {})[str(name)] = str(value)
    return by_domain

class FileCookieStore:
    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir

    def get_google_cookies(self, required_cookie_name: str = "__Secure-1PSID") -> Cookies:
        if not self.cookies_dir.exists() or not self.cookies_dir.is_dir():
            raise AuthenticationError(f"Cookies directory not found: {self.cookies_dir}")

        merged: Dict[str, Cookies] = {}
        for entry in self.cookies_dir.iterdir():
            if not entry.is_file() or entry.suffix.lower() != ".json":
                continue
            try:
                parsed = parse_exported_cookie_list(json.loads(entry.read_bytes()))
            except Exception:
                continue
            for domain, cookies in parsed.items():
                merged.setdefault(domain, {}).update(cookies)

        combined: Cookies = {}
        for domain, cookies in merged.items():
            if domain == "google.com" or domain.endswith(".google.com"):
                combined.update(cookies)

        if required_cookie_name and not combined.get(required_cookie_name):
            raise AuthenticationError(f"Missing required cookie: {required_cookie_name}")

        return combined
