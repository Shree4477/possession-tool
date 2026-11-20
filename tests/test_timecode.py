"""Tests for presentation-time formatting."""

import unittest

from possession_qc.timecode import format_timestamp


class FormatTimestampTests(unittest.TestCase):
    """Verify stable millisecond timestamp formatting."""

    def test_formats_sub_hour_timestamp(self) -> None:
        """Format sub-hour values without an hour component."""
        self.assertEqual(format_timestamp(772.43), "12:52.430")

    def test_formats_hour_timestamp(self) -> None:
        """Include hours for long match videos."""
        self.assertEqual(format_timestamp(7322.125), "02:02:02.125")

    def test_rounds_to_nearest_millisecond(self) -> None:
        """Round presentation seconds at the millisecond boundary."""
        self.assertEqual(format_timestamp(59.9996), "01:00.000")

    def test_rejects_negative_timestamp(self) -> None:
        """Reject negative positions rather than rendering misleading text."""
        with self.assertRaises(ValueError):
            format_timestamp(-0.001)

