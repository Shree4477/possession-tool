"""Presentation-time formatting helpers."""

import math


def format_timestamp(seconds: float) -> str:
    """Format non-negative seconds as an hour-aware millisecond timestamp."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("seconds must be a finite non-negative value")

    total_milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)

    if hours:
        return "%02d:%02d:%02d.%03d" % (hours, minutes, whole_seconds, milliseconds)
    return "%02d:%02d.%03d" % (minutes, whole_seconds, milliseconds)

