from typing import Optional, Dict
from gemini_flow.domain.interfaces import ISessionStore
from gemini_flow.domain.entities import SessionData

class FakeSessionStore(ISessionStore):
    def __init__(self, initial_sessions: Optional[Dict[str, SessionData]] = None):
        self.sessions: Dict[str, SessionData] = dict(initial_sessions or {})

    def load(self, session_id: str) -> Optional[SessionData]:
        return self.sessions.get(session_id)

    def save(self, data: SessionData) -> None:
        self.sessions[data.session_id] = data
