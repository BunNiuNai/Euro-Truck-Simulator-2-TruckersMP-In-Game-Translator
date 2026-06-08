"""Shared dataclass types for the translator message pipeline."""
from dataclasses import dataclass, field


@dataclass
class DisplayMessage:
    """A message ready for display in the overlay window."""
    player_name: str
    original_text: str
    translated_text: str
    is_self: bool = False
    baidu_fixed: bool = False  # True if Baidu override was applied


@dataclass
class TranslationStats:
    """Translation statistics for the stats bar."""
    translated: int = 0
    cached: int = 0
    self_skipped: int = 0

    @property
    def total(self) -> int:
        return self.translated + self.cached + self.self_skipped

    def savings_pct(self) -> str:
        if self.total == 0:
            return "0%"
        return f"{int((self.cached + self.self_skipped) / self.total * 100)}%"
