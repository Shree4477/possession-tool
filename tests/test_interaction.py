"""Tests for the derived possession interaction state machine."""

import unittest
from typing import List

from possession_qc.domain import (
    InteractionMode,
    Possession,
    resolve_interaction_state,
)


def possessions() -> List[Possession]:
    """Return two ranges separated by a valid gap."""
    return [
        Possession(1, 10, 1.0, 19, 1.9),
        Possession(2, 30, 3.0, 39, 3.9),
    ]


class InteractionStateTests(unittest.TestCase):
    """Verify the three current-frame interaction modes and their precedence."""

    def test_resolves_no_possession_in_gap(self) -> None:
        """Treat a frame between possessions as no possession."""
        state = resolve_interaction_state(possessions(), 25, None)

        self.assertEqual(state.mode, InteractionMode.NO_POSSESSION)
        self.assertIsNone(state.active_index)

    def test_resolves_active_possession_and_source_index(self) -> None:
        """Identify the exact possession containing the current frame."""
        state = resolve_interaction_state(possessions(), 30, None)

        self.assertEqual(state.mode, InteractionMode.ACTIVE_POSSESSION)
        self.assertEqual(state.active_index, 1)

    def test_new_possession_takes_precedence(self) -> None:
        """Keep creation mode while navigating after a new start was recorded."""
        state = resolve_interaction_state(possessions(), 30, 20)

        self.assertEqual(state.mode, InteractionMode.NEW_POSSESSION)
        self.assertIsNone(state.active_index)

    def test_missing_current_frame_is_no_possession(self) -> None:
        """Remain idle until an exact current frame is available."""
        state = resolve_interaction_state(possessions(), None, None)

        self.assertEqual(state.mode, InteractionMode.NO_POSSESSION)
