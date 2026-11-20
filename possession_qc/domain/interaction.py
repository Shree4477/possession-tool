"""Derived interaction states for current-frame possession workflows."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from possession_qc.domain.possession import Possession


class InteractionMode(Enum):
    """Describe the possession context at the exact current frame."""

    NO_POSSESSION = "no-possession"
    NEW_POSSESSION = "new-possession"
    ACTIVE_POSSESSION = "active-possession"


@dataclass(frozen=True)
class InteractionState:
    """Hold a derived interaction mode and containing possession index."""

    mode: InteractionMode
    active_index: Optional[int] = None


def resolve_interaction_state(
    possessions: Sequence[Possession],
    current_frame: Optional[int],
    new_possession_start_frame: Optional[int],
) -> InteractionState:
    """Resolve pending creation first, then existing containment, then a gap."""
    if new_possession_start_frame is not None:
        return InteractionState(InteractionMode.NEW_POSSESSION)
    if current_frame is not None:
        for index, possession in enumerate(possessions):
            if possession.start_frame <= current_frame <= possession.end_frame:
                return InteractionState(InteractionMode.ACTIVE_POSSESSION, index)
    return InteractionState(InteractionMode.NO_POSSESSION)
