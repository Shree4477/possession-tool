"""Native-window libmpv playback backend."""

import locale
from pathlib import Path
from typing import Callable, Optional

import mpv

from possession_qc.player.base import VideoPlayer


class NativeMpvPlayer(VideoPlayer):
    """Render libmpv video into an existing Win32 or X11 native window."""

    def __init__(self, window_id: int, on_time_changed: Callable[[float], None]) -> None:
        """Create an audio-free libmpv instance attached to ``window_id``."""
        locale.setlocale(locale.LC_NUMERIC, "C")
        self._on_time_changed = on_time_changed
        self._closed = False
        self._player = mpv.MPV(
            wid=str(window_id),
            audio="no",
            pause=True,
            keep_open="yes",
            idle="yes",
            input_default_bindings=False,
            input_vo_keyboard=False,
            framedrop="no",
            hr_seek_framedrop=False,
            interpolation=False,
            deinterlace=False,
            osc=False,
            terminal=False,
            config=False,
        )

        def time_observer(property_name: str, value: Optional[float]) -> None:
            """Forward a python-mpv property update to this player instance."""
            self._handle_time_position(property_name, value)

        self._time_observer = self._player.property_observer("time-pos")(
            time_observer
        )

    def load(self, video_path: Path) -> None:
        """Load ``video_path`` and pause when its first frame is available."""
        self._ensure_open()
        self._player.pause = True
        self._player.play(str(video_path.resolve()))

    def toggle_playback(self) -> None:
        """Toggle libmpv's pause property."""
        self._ensure_open()
        self._player.pause = not bool(self._player.pause)

    def seek_relative(self, seconds: float) -> None:
        """Seek relative to the current presentation time with exact seeking."""
        self._ensure_open()
        self._player.command("seek", seconds, "relative+exact")

    def seek_absolute(self, seconds: float) -> None:
        """Seek to an absolute position on mpv's normalized video timeline."""
        self._ensure_open()
        self._player.pause = True
        self._player.command("seek", seconds, "absolute+exact")

    def step_forward(self) -> None:
        """Pause playback and advance by one frame."""
        self._ensure_open()
        self._player.pause = True
        self._player.command("frame-step")

    def step_backward(self) -> None:
        """Pause playback and move backward by one frame."""
        self._ensure_open()
        self._player.pause = True
        self._player.command("frame-back-step")

    def close(self) -> None:
        """Terminate libmpv once and release the native child window."""
        if self._closed:
            return
        self._closed = True
        self._player.terminate()

    def _handle_time_position(self, _property_name: str, value: Optional[float]) -> None:
        """Forward valid presentation-time updates to the UI callback."""
        if value is not None and not self._closed:
            self._on_time_changed(float(value))

    def _ensure_open(self) -> None:
        """Raise a clear error when an operation follows player shutdown."""
        if self._closed:
            raise RuntimeError("video player is already closed")
