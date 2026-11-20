"""Schema-neutral possession mapping document."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MappingDocument:
    """Hold a loaded mapping and its unsaved-change state."""

    path: Path
    data: Any
    dirty: bool = False

    def mark_dirty(self) -> None:
        """Record that the in-memory mapping differs from its saved file."""
        self.dirty = True

    def mark_clean(self) -> None:
        """Record that the in-memory mapping matches its saved file."""
        self.dirty = False

