"""Replaceable exact-frame index provider interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

from possession_qc.frame_index.model import FrameIndex


FrameIndexProgressCallback = Callable[[float, float], None]


class FrameIndexProvider(ABC):
    """Build an exact frame index from a local video source."""

    @abstractmethod
    def build(
        self,
        video_path: Path,
        progress_callback: Optional[FrameIndexProgressCallback] = None,
    ) -> FrameIndex:
        """Decode frame timestamps and optionally report processed/total seconds."""

    @abstractmethod
    def cancel(self) -> None:
        """Request cancellation of an in-progress build, if any."""
