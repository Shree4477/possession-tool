"""Video-player interface used by the application layer."""

from abc import ABC, abstractmethod
from pathlib import Path


class VideoPlayer(ABC):
    """Abstract playback operations required by the correction workflow."""

    @abstractmethod
    def load(self, video_path: Path) -> None:
        """Load a local video and leave it paused at its initial frame."""

    @abstractmethod
    def toggle_playback(self) -> None:
        """Toggle between playing and paused states."""

    @abstractmethod
    def seek_relative(self, seconds: float) -> None:
        """Seek by a signed number of seconds using precise seeking."""

    @abstractmethod
    def seek_absolute(self, seconds: float) -> None:
        """Seek to an absolute normalized presentation time in seconds."""

    @abstractmethod
    def step_forward(self) -> None:
        """Pause and advance by one presented video frame."""

    @abstractmethod
    def step_backward(self) -> None:
        """Pause and move backward by one presented video frame."""

    @abstractmethod
    def close(self) -> None:
        """Release all player and native video resources."""
