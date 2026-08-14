import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from gemini_flow.domain.entities import ChatRequest

class AILogger:
    def __init__(self, runtime_dir: Optional[Path] = None):
        if runtime_dir is None:
            # Default to .runtime in project root
            # Path(__file__).parent is logging, parent is infrastructure, parent is gemini_flow, parent is project root
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self.runtime_dir = project_root / ".runtime"
        else:
            self.runtime_dir = runtime_dir
            
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def log_interaction(self, request: ChatRequest, response_text: str, response_images: Optional[List[str]] = None) -> Path:
        """
        Logs the AI interaction into the .runtime directory.
        """
        if response_images is None:
            response_images = []
            
        now = datetime.now()
        timestamp_full = now.strftime("%Y%m%d_%H%M%S")
        
        # Extract basic metadata
        metadata = {
            "model": request.model,
            "language": request.language,
            "session_id": request.session_id,
            "has_input_images": len(request.images) > 0,
            "timestamp": now.isoformat()
        }
        
        log_data = {
            "request": {
                "prompt": request.prompt,
                "system_prompt": request.system_prompt
            },
            "response": {
                "text": response_text,
                "images": response_images
            },
            "metadata": metadata
        }
        
        filename = f"gemini_{timestamp_full}_log.json"
        log_path = self.runtime_dir / filename
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
            
        return log_path
