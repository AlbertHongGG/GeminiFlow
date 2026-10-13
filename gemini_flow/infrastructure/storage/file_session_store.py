import json
from pathlib import Path
from typing import Optional
from gemini_flow.domain.entities import SessionData
from gemini_flow.domain.interfaces import ISessionStore

class FileSessionStore(ISessionStore):
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return self.storage_dir / f"{safe_id}.json"

    def load(self, session_id: str) -> Optional[SessionData]:
        path = self._get_path(session_id)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            return SessionData.model_validate_json(raw)
        except Exception:
            return None

    def save(self, data: SessionData) -> None:
        path = self._get_path(data.session_id)
        path.write_text(data.model_dump_json(indent=2), encoding="utf-8")
