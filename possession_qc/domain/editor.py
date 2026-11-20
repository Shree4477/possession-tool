"""Possession editing rules independent of the Qt user interface."""

from dataclasses import dataclass, replace
from typing import Callable, List, Optional, Sequence, Tuple

from possession_qc.domain.possession import Possession


FrameTimestampLookup = Callable[[int], float]


class PossessionEditError(ValueError):
    """Report an edit that would produce an invalid possession mapping."""


@dataclass(frozen=True)
class PossessionEditResult:
    """Return edited possessions and the item that should remain selected."""

    possessions: List[Possession]
    selected_index: Optional[int]


class PossessionEditor:
    """Apply inclusive-frame edits and keep possessions ordered and numbered."""

    def create(
        self,
        possessions: Sequence[Possession],
        start_frame: int,
        end_frame: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Create and select a possession covering the inclusive frame range."""
        if end_frame < start_frame:
            raise PossessionEditError(
                "Current frame must not precede the new possession start."
            )
        created = Possession(
            possession_num=possessions[0].possession_num if possessions else 1,
            start_frame=start_frame,
            start_time=timestamp_for_frame(start_frame),
            end_frame=end_frame,
            end_time=timestamp_for_frame(end_frame),
        )
        edited = list(possessions) + [created]
        return self._finalize(edited, created)

    def delete(
        self, possessions: Sequence[Possession], selected_index: int
    ) -> PossessionEditResult:
        """Delete one possession and clear the current selection."""
        self._selected(possessions, selected_index)
        edited = list(possessions)
        del edited[selected_index]
        return self._finalize(edited, None)

    def split(
        self,
        possessions: Sequence[Possession],
        selected_index: int,
        current_frame: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Split before ``current_frame`` and select the new right possession."""
        selected = self._selected(possessions, selected_index)
        if current_frame <= selected.start_frame or current_frame > selected.end_frame:
            raise PossessionEditError(
                "Current frame must be after the possession start and no later than its end."
            )
        left = replace(
            selected,
            end_frame=current_frame - 1,
            end_time=timestamp_for_frame(current_frame - 1),
            extra_fields=dict(selected.extra_fields),
        )
        right = replace(
            selected,
            start_frame=current_frame,
            start_time=timestamp_for_frame(current_frame),
            extra_fields=dict(selected.extra_fields),
        )
        edited = list(possessions)
        edited[selected_index : selected_index + 1] = [left, right]
        return self._finalize(edited, right)

    def join_next(
        self,
        possessions: Sequence[Possession],
        selected_index: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Join the selected possession through the next possession's end."""
        selected = self._selected(possessions, selected_index)
        if selected_index + 1 >= len(possessions):
            raise PossessionEditError("The current possession has no next possession.")
        following = possessions[selected_index + 1]
        joined = replace(
            selected,
            end_frame=following.end_frame,
            end_time=timestamp_for_frame(following.end_frame),
            extra_fields=dict(selected.extra_fields),
        )
        edited = list(possessions)
        edited[selected_index : selected_index + 2] = [joined]
        return self._finalize(edited, joined)

    def join_previous(
        self,
        possessions: Sequence[Possession],
        selected_index: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Join the previous possession through the selected possession's end."""
        selected = self._selected(possessions, selected_index)
        if selected_index <= 0:
            raise PossessionEditError("The current possession has no previous possession.")
        previous = possessions[selected_index - 1]
        joined = replace(
            previous,
            end_frame=selected.end_frame,
            end_time=timestamp_for_frame(selected.end_frame),
            extra_fields=dict(previous.extra_fields),
        )
        edited = list(possessions)
        edited[selected_index - 1 : selected_index + 1] = [joined]
        return self._finalize(edited, joined)

    def set_start(
        self,
        possessions: Sequence[Possession],
        selected_index: int,
        frame_number: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Move the selected possession's inclusive start to ``frame_number``."""
        selected = self._selected(possessions, selected_index)
        if frame_number > selected.end_frame:
            raise PossessionEditError("Possession start cannot follow possession end.")
        changed = replace(
            selected,
            start_frame=frame_number,
            start_time=timestamp_for_frame(frame_number),
            extra_fields=dict(selected.extra_fields),
        )
        edited = list(possessions)
        edited[selected_index] = changed
        return self._finalize(edited, changed)

    def set_end(
        self,
        possessions: Sequence[Possession],
        selected_index: int,
        frame_number: int,
        timestamp_for_frame: FrameTimestampLookup,
    ) -> PossessionEditResult:
        """Move the selected possession's inclusive end to ``frame_number``."""
        selected = self._selected(possessions, selected_index)
        if frame_number < selected.start_frame:
            raise PossessionEditError("Possession end cannot precede possession start.")
        changed = replace(
            selected,
            end_frame=frame_number,
            end_time=timestamp_for_frame(frame_number),
            extra_fields=dict(selected.extra_fields),
        )
        edited = list(possessions)
        edited[selected_index] = changed
        return self._finalize(edited, changed)

    def overlaps(
        self, possessions: Sequence[Possession]
    ) -> List[Tuple[Possession, Possession]]:
        """Return adjacent overlaps after ordering possessions by start frame."""
        ordered = sorted(possessions, key=lambda item: item.start_frame)
        return [
            (left, right)
            for left, right in zip(ordered, ordered[1:])
            if right.start_frame <= left.end_frame
        ]

    def _selected(
        self, possessions: Sequence[Possession], selected_index: int
    ) -> Possession:
        """Return a selected possession or report a stale selection index."""
        if selected_index < 0 or selected_index >= len(possessions):
            raise PossessionEditError("No current possession is selected.")
        return possessions[selected_index]

    def _finalize(
        self,
        possessions: Sequence[Possession],
        selected: Optional[Possession],
    ) -> PossessionEditResult:
        """Order, reject overlaps, renumber, and locate the selected object."""
        ordered = sorted(possessions, key=lambda item: item.start_frame)
        overlaps = self.overlaps(ordered)
        if overlaps:
            left, right = overlaps[0]
            raise PossessionEditError(
                "Possessions %d and %d would overlap."
                % (left.possession_num, right.possession_num)
            )

        first_number = 0 if ordered and ordered[0].possession_num == 0 else 1
        renumbered = [
            replace(item, possession_num=first_number + index)
            for index, item in enumerate(ordered)
        ]
        selected_index = None
        if selected is not None:
            selected_index = next(
                index for index, item in enumerate(ordered) if item is selected
            )
        return PossessionEditResult(renumbered, selected_index)
