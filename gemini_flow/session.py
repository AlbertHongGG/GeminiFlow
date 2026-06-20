import json
import os
from pathlib import Path
from typing import Optional, Sequence

class SessionStore:
    def __init__(self, storage_dir: str = "output/sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, session_id: str) -> Path:
        # Sanitize session_id to prevent directory traversal
        safe_id = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return self.storage_dir / f"{safe_id}.json"

    def load(self, session_id: str) -> Optional[Sequence[str]]:
        path = self._get_path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) >= 2:
                return data
        except Exception:
            pass
        return None

    def save(self, session_id: str, conversation_ids: Sequence[str]) -> None:
        path = self._get_path(session_id)
        path.write_text(json.dumps(conversation_ids, ensure_ascii=False), encoding="utf-8")
