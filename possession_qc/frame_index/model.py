"""Compact frame-number to presentation-timestamp mapping."""

from array import array
from bisect import bisect_left
from dataclasses import dataclass


class FrameIndexError(ValueError):
    """Report video timestamp data that cannot provide an exact frame mapping."""


@dataclass
class FrameIndex:
    """Map zero-indexed decoded frames to strictly increasing integer PTS values."""

    time_base_numerator: int
    time_base_denominator: int
    timestamps: array

    def __post_init__(self) -> None:
        """Validate time base and presentation-order timestamp invariants."""
        if self.time_base_numerator <= 0 or self.time_base_denominator <= 0:
            raise FrameIndexError("frame index time base must be positive")
        if self.timestamps.typecode != "q":
            raise FrameIndexError("frame index timestamps must use signed 64-bit storage")
        if not self.timestamps:
            raise FrameIndexError("frame index cannot be empty")

        previous = self.timestamps[0]
        for frame_number in range(1, len(self.timestamps)):
            current = self.timestamps[frame_number]
            if current <= previous:
                raise FrameIndexError(
                    "frame timestamps are duplicate or non-monotonic at frame %d"
                    % frame_number
                )
            previous = current

    @property
    def frame_count(self) -> int:
        """Return the total number of indexed decoded frames."""
        return len(self.timestamps)

    def timestamp_seconds(self, frame_number: int) -> float:
        """Return a frame's presentation time on mpv's zero-based timeline."""
        self._validate_frame_number(frame_number)
        timestamp_delta = self.timestamps[frame_number] - self.timestamps[0]
        return (
            timestamp_delta
            * self.time_base_numerator
            / self.time_base_denominator
        )

    def frame_for_seconds(self, seconds: float) -> int:
        """Return the frame whose normalized PTS is nearest to ``seconds``."""
        target_timestamp = self.timestamps[0] + round(
            seconds * self.time_base_denominator / self.time_base_numerator
        )
        insertion = bisect_left(self.timestamps, target_timestamp)
        if insertion <= 0:
            return 0
        if insertion >= len(self.timestamps):
            return len(self.timestamps) - 1

        previous = insertion - 1
        previous_distance = target_timestamp - self.timestamps[previous]
        next_distance = self.timestamps[insertion] - target_timestamp
        return previous if previous_distance <= next_distance else insertion

    def _validate_frame_number(self, frame_number: int) -> None:
        """Reject booleans and frame numbers outside the indexed stream."""
        if isinstance(frame_number, bool) or not isinstance(frame_number, int):
            raise TypeError("frame_number must be an integer")
        if frame_number < 0 or frame_number >= len(self.timestamps):
            raise IndexError("frame_number is outside the frame index")

