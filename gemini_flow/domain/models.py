from __future__ import annotations
from enum import Enum, IntEnum
from typing import Optional, Union
from pydantic import BaseModel

class ModelFamily(str, Enum):
    FLASH_LITE = "flash-lite"
    FLASH = "flash"
    PRO = "pro"
    ARGON = "argon"

    @property
    def model_id(self) -> int:
        if self in (ModelFamily.FLASH, ModelFamily.FLASH_LITE):
            return 1
        if self == ModelFamily.PRO:
            return 3
        if self == ModelFamily.ARGON:
            return 8
        return 1

    @property
    def model_hash(self) -> str:
        if self == ModelFamily.FLASH_LITE:
            return "fbb127bbb056c959"
        if self == ModelFamily.FLASH:
            return "56fdd199312815e2"
        if self == ModelFamily.PRO:
            return "e6fa609c3fa255c0"
        if self == ModelFamily.ARGON:
            return "95a4c0abcba24364"
        return "56fdd199312815e2"


class ThinkingLevel(IntEnum):
    LOW = 1
    MEDIUM = 4
    HIGH = 2

    @classmethod
    def from_value(cls, val: Optional[Union[ThinkingLevel, str, int]]) -> ThinkingLevel:
        if val is None:
            return cls.LOW
        if isinstance(val, ThinkingLevel):
            return val
        if isinstance(val, int):
            for level in cls:
                if level.value == val:
                    return level
            return cls.LOW

        s = str(val).strip().lower()
        if s in ("4", "medium", "med", "mid"):
            return cls.MEDIUM
        if s in ("2", "high", "on", "true"):
            return cls.HIGH
        # Default / off / low
        return cls.LOW


class ModelSpec(BaseModel):
    family: ModelFamily
    thinking: ThinkingLevel
    raw_name: str

    @property
    def model_id(self) -> int:
        return self.family.model_id

    @property
    def model_hash(self) -> str:
        return self.family.model_hash

    @property
    def thinking_level(self) -> int:
        return self.thinking.value

    @classmethod
    def resolve(
        cls,
        model_name: Optional[str] = None,
        thinking: Optional[Union[ThinkingLevel, str, int]] = None,
    ) -> ModelSpec:
        raw = (model_name or "gemini-3.8-flash").strip()
        lower = raw.lower()

        # Determine family strictly from model identity
        if any(k in lower for k in ("argon", "gemini-4", "gemini4")):
            family = ModelFamily.ARGON
        elif "lite" in lower:
            family = ModelFamily.FLASH_LITE
        elif "pro" in lower:
            family = ModelFamily.PRO
        else:
            family = ModelFamily.FLASH

        # Determine thinking level strictly from thinking parameter
        thinking_lvl = ThinkingLevel.from_value(thinking)

        return cls(family=family, thinking=thinking_lvl, raw_name=raw)
