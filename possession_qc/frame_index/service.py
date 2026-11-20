"""Frame-index cache/provider orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from possession_qc.frame_index.cache import FrameIndexCache
from possession_qc.frame_index.model import FrameIndex
from possession_qc.frame_index.provider import (
    FrameIndexProgressCallback,
    FrameIndexProvider,
)


@dataclass(frozen=True)
class FrameIndexResult:
    """Describe a resolved frame index and whether it came from cache."""

    frame_index: FrameIndex
    from_cache: bool
    cache_warning: str = ""


class FrameIndexService:
    """Resolve cached frame indexes or build them through a provider."""

    def __init__(self, provider: FrameIndexProvider, cache: FrameIndexCache) -> None:
        """Create the service with replaceable provider and cache implementations."""
        self._provider = provider
        self._cache = cache

    def get_or_build(
        self,
        video_path: Path,
        progress_callback: Optional[FrameIndexProgressCallback] = None,
    ) -> FrameIndexResult:
        """Return a valid cached index or build and best-effort cache a new one."""
        cached = self._cache.load(video_path)
        if cached is not None:
            return FrameIndexResult(frame_index=cached, from_cache=True)

        frame_index = self._provider.build(video_path, progress_callback)
        try:
            self._cache.save(video_path, frame_index)
        except OSError as error:
            return FrameIndexResult(
                frame_index=frame_index,
                from_cache=False,
                cache_warning="Frame index could not be cached: %s" % error,
            )
        return FrameIndexResult(frame_index=frame_index, from_cache=False)

    def cancel(self) -> None:
        """Forward cancellation to the configured frame-index provider."""
        self._provider.cancel()
