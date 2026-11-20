"""Core possession-correction domain models."""

from possession_qc.domain.editor import (
    PossessionEditError,
    PossessionEditResult,
    PossessionEditor,
)
from possession_qc.domain.interaction import (
    InteractionMode,
    InteractionState,
    resolve_interaction_state,
)
from possession_qc.domain.possession import Possession

__all__ = [
    "Possession",
    "PossessionEditError",
    "PossessionEditResult",
    "PossessionEditor",
    "InteractionMode",
    "InteractionState",
    "resolve_interaction_state",
]
