"""Tests for inclusive possession editing rules."""

import unittest
from typing import List

from possession_qc.domain import Possession, PossessionEditError, PossessionEditor


def timestamp_for_frame(frame_number: int) -> float:
    """Provide deterministic test timestamps without assuming an application FPS."""
    return frame_number / 10.0


def possessions() -> List[Possession]:
    """Return two disjoint one-based possessions for each test."""
    return [
        Possession(1, 10, 1.0, 19, 1.9),
        Possession(2, 30, 3.0, 39, 3.9),
    ]


class PossessionEditorTests(unittest.TestCase):
    """Verify editing, overlap rejection, timestamps, and renumbering."""

    def setUp(self) -> None:
        """Create the stateless editor used by each test."""
        self.editor = PossessionEditor()

    def test_creates_sorted_possession_and_selects_it(self) -> None:
        """Insert a new range in frame order and derive its timestamps."""
        result = self.editor.create(possessions(), 21, 25, timestamp_for_frame)

        self.assertEqual([item.possession_num for item in result.possessions], [1, 2, 3])
        self.assertEqual(result.selected_index, 1)
        self.assertEqual(result.possessions[1].start_time, 2.1)
        self.assertEqual(result.possessions[1].end_time, 2.5)

    def test_rejects_creation_overlap(self) -> None:
        """Reject a new inclusive range sharing a frame with another possession."""
        with self.assertRaisesRegex(PossessionEditError, "overlap"):
            self.editor.create(possessions(), 19, 25, timestamp_for_frame)

    def test_splits_before_current_frame(self) -> None:
        """Put the frame before current on the left and current on the right."""
        result = self.editor.split(possessions(), 0, 15, timestamp_for_frame)

        self.assertEqual(
            [(item.start_frame, item.end_frame) for item in result.possessions],
            [(10, 14), (15, 19), (30, 39)],
        )
        self.assertEqual(result.selected_index, 1)

    def test_rejects_empty_split_side(self) -> None:
        """Reject splitting before the first frame of a possession."""
        with self.assertRaises(PossessionEditError):
            self.editor.split(possessions(), 0, 10, timestamp_for_frame)

    def test_joins_across_a_valid_gap(self) -> None:
        """Join selected and next into one inclusive range and retain selection."""
        result = self.editor.join_next(possessions(), 0, timestamp_for_frame)

        self.assertEqual(len(result.possessions), 1)
        self.assertEqual((result.possessions[0].start_frame, result.possessions[0].end_frame), (10, 39))
        self.assertEqual(result.selected_index, 0)

    def test_set_start_rejects_previous_overlap(self) -> None:
        """Reject stretching a possession start into the previous possession."""
        with self.assertRaisesRegex(PossessionEditError, "overlap"):
            self.editor.set_start(possessions(), 1, 19, timestamp_for_frame)

    def test_set_end_allows_inclusive_single_frame(self) -> None:
        """Allow a possession to shrink to one inclusive frame."""
        result = self.editor.set_end(possessions(), 0, 10, timestamp_for_frame)

        self.assertEqual(result.possessions[0].duration_frames, 1)
        self.assertEqual(result.possessions[0].end_time, 1.0)

    def test_delete_renumbers_and_clears_selection(self) -> None:
        """Renumber remaining possessions and avoid implicit post-delete selection."""
        result = self.editor.delete(possessions(), 0)

        self.assertEqual([item.possession_num for item in result.possessions], [1])
        self.assertIsNone(result.selected_index)
