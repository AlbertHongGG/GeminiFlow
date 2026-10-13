from __future__ import annotations
import json
from typing import List, Tuple, Sequence, Optional, Dict, Any
from gemini_flow.domain.models import ModelSpec

class GeminiPayloadBuilder:
    """
    Constructs the 99-element inner Protobuf/JSPB array for Gemini StreamGenerate requests.
    Eliminates magic numbers by assigning named semantic constants conforming to
    the latest October 2026 wire protocol specification.
    """

    ARRAY_LENGTH = 99

    # Named indices in inner_req
    IDX_PROMPT_BLOCK = 0
    IDX_LANGUAGE = 1
    IDX_TURN_INDEX = 17
    IDX_CAPABILITIES = 30
    IDX_REQ_UUID = 59
    IDX_CONVERSATION_CONTEXT = 71
    IDX_MODEL_ID = 79
    IDX_THINKING_LEVEL = 80
    IDX_NEW_SESSION_FLAG = 96

    def __init__(
        self,
        prompt: str,
        system_prompt: Optional[str],
        language: str,
        model_spec: ModelSpec,
        req_uuid: str,
        uploads: Optional[Sequence[Tuple[str, str]]] = None,
        conversation_id: Optional[str] = None,
        continuation_token: Optional[str] = None,
        turn_index: int = 0,
    ):
        self.prompt = prompt
        if system_prompt:
            self.prompt = f"System:\n{system_prompt}\n\nUser:\n{prompt}"
            
        self.language = language
        self.model_spec = model_spec
        self.req_uuid = req_uuid
        self.uploads = uploads or []
        self.conversation_id = conversation_id
        self.continuation_token = continuation_token
        self.turn_index = turn_index

    def _build_image_list(self) -> Optional[List[Any]]:
        if not self.uploads:
            return None
        return [
            [[upload_ref, 1], image_name] for upload_ref, image_name in self.uploads
        ]

    def _build_conversation_context(self) -> Optional[List[Any]]:
        """
        Builds the 8-element conversation continuation block for arr[71].
        [conv_id, None, None, None, None, None, None, continuation_token]
        Only populated on turn_index > 0 when a conversation_id is available.
        """
        if self.turn_index == 0 or not self.conversation_id:
            return None
        return [
            self.conversation_id,
            None,
            None,
            None,
            None,
            None,
            None,
            self.continuation_token,
        ]

    def build_inner_array(self) -> List[Any]:
        """
        Builds the complete 99-element Protobuf/JSPB request array.
        """
        arr: List[Any] = [None] * self.ARRAY_LENGTH

        # 0: Prompt block
        arr[self.IDX_PROMPT_BLOCK] = [
            self.prompt,
            0,
            None,
            self._build_image_list(),
            None,
            None,
            0,
        ]

        # 1: Language block
        arr[self.IDX_LANGUAGE] = [self.language]

        # Standard static protocol flags
        arr[6] = [0]
        arr[7] = 1
        arr[10] = 1
        arr[11] = 0

        # 17: Turn sequence index [[0]], [[1]], etc.
        arr[self.IDX_TURN_INDEX] = [[self.turn_index]]
        arr[18] = 0
        arr[27] = 1

        # 30: Feature capability flags
        arr[self.IDX_CAPABILITIES] = [4, 16, 19]
        arr[41] = [1]
        arr[49] = 0
        arr[53] = 0

        # 59: Request UUID matching Header x-goog-ext-525005358-jspb
        arr[self.IDX_REQ_UUID] = self.req_uuid
        arr[61] = []
        arr[67] = 0
        arr[68] = 1

        # 71: Conversation continuation context
        arr[self.IDX_CONVERSATION_CONTEXT] = self._build_conversation_context()

        # 79 & 80: Model routing ID and Thinking level
        arr[self.IDX_MODEL_ID] = self.model_spec.model_id
        arr[self.IDX_THINKING_LEVEL] = self.model_spec.thinking_level

        # End flags
        arr[91] = 1
        # 96: 0 for new session (turn 0), 1 for continuing session (turn > 0)
        arr[self.IDX_NEW_SESSION_FLAG] = 0 if self.turn_index == 0 else 1
        arr[98] = 1

        return arr

    def build_post_data(self, at_token: str) -> Dict[str, str]:
        """
        Builds the form postData payload containing 'at' and 'f.req'.
        """
        inner = self.build_inner_array()
        return {
            "at": at_token,
            "f.req": json.dumps([None, json.dumps(inner, separators=(",", ":"))], separators=(",", ":")),
        }
