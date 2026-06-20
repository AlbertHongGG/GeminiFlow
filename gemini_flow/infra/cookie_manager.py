from pathlib import Path
import json
from typing import Dict
from ..exceptions import AuthenticationError
from ..config import GOOGLE_COOKIE_DOMAIN, REQUIRED_COOKIE_NAME

Cookies = Dict[str, str]

def load_json(path: Path) -> object:
    with path.open("rb") as f:
        return json.load(f)

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

def load_cookies_from_dir(cookies_dir: Path) -> Dict[str, Cookies]:
    merged: Dict[str, Cookies] = {}
    for entry in cookies_dir.iterdir():
        if not entry.is_file() or entry.suffix.lower() != ".json":
            continue
        try:
            parsed = parse_exported_cookie_list(load_json(entry))
        except Exception:
            continue
        for domain, cookies in parsed.items():
            merged.setdefault(domain, {}).update(cookies)
    return merged

def pick_google_cookies(cookies_by_domain: Dict[str, Cookies]) -> Cookies:
    if GOOGLE_COOKIE_DOMAIN in cookies_by_domain:
        return dict(cookies_by_domain[GOOGLE_COOKIE_DOMAIN])

    combined: Cookies = {}
    for domain, cookies in cookies_by_domain.items():
        if domain.endswith("google.com"):
            combined.update(cookies)
    return combined

class CookieManager:
    def __init__(self, cookies_dir: Path):
        self.cookies_dir = cookies_dir

    def get_google_cookies(self) -> Cookies:
        if not self.cookies_dir.exists() or not self.cookies_dir.is_dir():
            raise AuthenticationError(f"cookies dir not found: {self.cookies_dir}")

        cookies_by_domain = load_cookies_from_dir(self.cookies_dir)
        cookies = pick_google_cookies(cookies_by_domain)

        if not cookies.get(REQUIRED_COOKIE_NAME):
            raise AuthenticationError(f"Missing required cookie: {REQUIRED_COOKIE_NAME}")

        return cookies
