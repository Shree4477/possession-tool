"""Basketball possession domain model."""

import math
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Possession:
    """Represent one inclusive frame range from a possession mapping."""

    possession_num: int
    start_frame: int
    start_time: float
    end_frame: int
    end_time: float
    extra_fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject structurally invalid values at the domain boundary."""
        if isinstance(self.possession_num, bool) or not isinstance(
            self.possession_num, int
        ):
            raise TypeError("possession_num must be an integer")
        if self.possession_num < 0:
            raise ValueError("possession_num cannot be negative")
        if isinstance(self.start_frame, bool) or not isinstance(self.start_frame, int):
            raise TypeError("start_frame must be an integer")
        if isinstance(self.end_frame, bool) or not isinstance(self.end_frame, int):
            raise TypeError("end_frame must be an integer")
        if self.start_frame < 0 or self.end_frame < 0:
            raise ValueError("possession frames cannot be negative")
        if self.end_frame < self.start_frame:
            raise ValueError("possession end_frame cannot precede start_frame")
        if not math.isfinite(self.start_time) or not math.isfinite(self.end_time):
            raise ValueError("possession timestamps must be finite")
        if self.start_time < 0 or self.end_time < 0:
            raise ValueError("possession timestamps cannot be negative")
        if self.end_time < self.start_time:
            raise ValueError("possession end_time cannot precede start_time")

    @property
    def duration_frames(self) -> int:
        """Return the inclusive number of frames in this possession."""
        return self.end_frame - self.start_frame + 1

