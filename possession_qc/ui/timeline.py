"""Compact frame-authoritative possession timeline widgets."""

from typing import List, Optional, Sequence, Set, Tuple

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPaintEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from possession_qc.domain import Possession


class PossessionTimeline(QWidget):
    """Draw possession ranges and map pointer clicks to exact frame numbers."""

    frame_clicked = Signal(int)
    fit_requested = Signal()

    def __init__(self, title: str, minimum_height: int) -> None:
        """Create an empty timeline with a compact heading."""
        super().__init__()
        self._title = title
        self._possessions: List[Possession] = []
        self._current_frame: Optional[int] = None
        self._new_possession_start_frame: Optional[int] = None
        self._selected_index: Optional[int] = None
        self._overlap_indices: Set[int] = set()
        self._total_frames = 0
        self._visible_start = 0
        self._visible_end = 0
        self._view_initialized = False
        self._follow_current_frame = False
        self.setMinimumHeight(minimum_height)
        self.setToolTip(
            "Mouse wheel zooms around the pointer; double-click fits the timeline"
        )

    def set_state(
        self,
        possessions: Sequence[Possession],
        current_frame: Optional[int],
        selected_index: Optional[int],
        total_frames: int,
        visible_start: int = 0,
        visible_end: Optional[int] = None,
        new_possession_start_frame: Optional[int] = None,
    ) -> None:
        """Replace all displayed state and schedule a repaint."""
        previous_total_frames = self._total_frames
        self._possessions = list(possessions)
        self._current_frame = current_frame
        self._new_possession_start_frame = new_possession_start_frame
        self._selected_index = selected_index
        self._overlap_indices = self._find_overlap_indices(self._possessions)
        self._total_frames = max(0, total_frames)
        if self._total_frames != previous_total_frames:
            self._view_initialized = False
        if self._total_frames == 0:
            self._visible_start = 0
            self._visible_end = 0
            self._view_initialized = False
        else:
            if not self._view_initialized:
                requested_end = (
                    self._total_frames - 1 if visible_end is None else visible_end
                )
                self.set_visible_range(visible_start, requested_end)
            elif self._follow_current_frame:
                self._follow_current_into_view()
        self.update()

    def set_visible_range(self, start_frame: int, end_frame: int) -> None:
        """Set and clamp the exact inclusive frame range shown by the widget."""
        if self._total_frames <= 0:
            self._visible_start = 0
            self._visible_end = 0
            self._view_initialized = False
            self.update()
            return
        self._visible_start = max(0, min(start_frame, self._total_frames - 1))
        self._visible_end = max(
            self._visible_start,
            min(end_frame, self._total_frames - 1),
        )
        self._view_initialized = True
        self.update()

    def fit_video(self) -> None:
        """Fit the entire indexed video into the timeline."""
        if self._total_frames > 0:
            self.set_visible_range(0, self._total_frames - 1)

    def set_follow_current_frame(self, enabled: bool) -> None:
        """Enable or disable automatic recentering when current frame leaves view."""
        self._follow_current_frame = enabled
        if enabled:
            self._follow_current_into_view()
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint ranges, active/current distinctions, and current-frame line."""
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        painter.setPen(QColor("#334155"))
        painter.drawText(8, 17, self._title)
        if self._total_frames > 0:
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRectF(8.0, 0.0, max(1.0, self.width() - 16.0), 21.0),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                "Frames %d–%d" % (self._visible_start, self._visible_end),
            )

        track = QRectF(8.0, 24.0, max(1.0, self.width() - 16.0), max(10.0, self.height() - 32.0))
        painter.fillRect(track, QColor("#e5e7eb"))
        if self._total_frames <= 0 or self._visible_end < self._visible_start:
            painter.setPen(QColor("#64748b"))
            painter.drawText(track, Qt.AlignmentFlag.AlignCenter, "No frame index")
            return

        for index, possession in enumerate(self._possessions):
            start = max(possession.start_frame, self._visible_start)
            end = min(possession.end_frame, self._visible_end)
            if start > end:
                continue
            left = self._frame_boundary_x(start, track)
            right = self._frame_boundary_x(end + 1, track)
            possession_rect = QRectF(left, track.top(), max(1.0, right - left), track.height())
            contains_current = (
                self._current_frame is not None
                and possession.start_frame <= self._current_frame <= possession.end_frame
            )
            if index in self._overlap_indices:
                fill = QColor("#ef4444")
            elif contains_current:
                fill = QColor("#22c55e")
            else:
                fill = QColor("#94a3b8")
            painter.fillRect(possession_rect, fill)
            if index == self._selected_index:
                painter.setPen(QPen(QColor("#2563eb"), 3.0))
                painter.drawRect(possession_rect.adjusted(1.5, 1.5, -1.5, -1.5))
            if possession_rect.width() >= 28.0:
                painter.setPen(QColor("#0f172a"))
                painter.drawText(
                    possession_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    str(possession.possession_num),
                )

        self._paint_new_possession_range(painter, track)

        if (
            self._current_frame is not None
            and self._visible_start <= self._current_frame <= self._visible_end
        ):
            current_x = self._frame_boundary_x(self._current_frame, track)
            painter.setPen(QPen(QColor("#dc2626"), 2.0))
            painter.drawLine(
                int(current_x),
                int(track.top()),
                int(current_x),
                int(track.bottom()),
            )

    def _paint_new_possession_range(
        self, painter: QPainter, track: QRectF
    ) -> None:
        """Overlay the tentative inclusive range during new-possession creation."""
        if (
            self._new_possession_start_frame is None
            or self._current_frame is None
        ):
            return
        range_start = min(self._new_possession_start_frame, self._current_frame)
        range_end = max(self._new_possession_start_frame, self._current_frame)
        visible_start = max(range_start, self._visible_start)
        visible_end = min(range_end, self._visible_end)
        if visible_start > visible_end:
            return
        left = self._frame_boundary_x(visible_start, track)
        right = self._frame_boundary_x(visible_end + 1, track)
        preview_rect = QRectF(
            left,
            track.top(),
            max(2.0, right - left),
            track.height(),
        )
        moves_forward = self._current_frame >= self._new_possession_start_frame
        fill = QColor(37, 99, 235, 180) if moves_forward else QColor(245, 158, 11, 190)
        border = QColor("#1d4ed8") if moves_forward else QColor("#b45309")
        painter.fillRect(preview_rect, fill)
        painter.setPen(QPen(border, 2.0))
        painter.drawRect(preview_rect.adjusted(1.0, 1.0, -1.0, -1.0))
        if preview_rect.width() >= 48.0:
            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                preview_rect,
                Qt.AlignmentFlag.AlignCenter,
                "NEW",
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Emit the exact frame corresponding to a left-button timeline click."""
        inside_track = (
            8.0 <= event.position().x() <= self.width() - 8.0
            and 24.0 <= event.position().y() <= self.height() - 8.0
        )
        if (
            event.button() != Qt.MouseButton.LeftButton
            or self._total_frames <= 0
            or not inside_track
        ):
            super().mousePressEvent(event)
            return
        track_left = 8.0
        track_width = max(1.0, self.width() - 16.0)
        fraction = max(0.0, min((event.position().x() - track_left) / track_width, 1.0))
        visible_count = self._visible_end - self._visible_start + 1
        frame_number = self._visible_start + min(
            int(fraction * visible_count), visible_count - 1
        )
        self.frame_clicked.emit(frame_number)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Request the timeline's context-appropriate fit operation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.fit_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zoom around the frame beneath the pointer while preserving exact bounds."""
        if self._total_frames <= 0 or event.angleDelta().y() == 0:
            super().wheelEvent(event)
            return
        current_count = self._visible_end - self._visible_start + 1
        minimum_count = min(10, self._total_frames)
        zoom_factor = 0.8 if event.angleDelta().y() > 0 else 1.25
        target_count = max(
            minimum_count,
            min(int(round(current_count * zoom_factor)), self._total_frames),
        )
        track_width = max(1.0, self.width() - 16.0)
        pointer_fraction = max(
            0.0,
            min((event.position().x() - 8.0) / track_width, 1.0),
        )
        anchor_frame = self._visible_start + pointer_fraction * current_count
        target_start = int(round(anchor_frame - pointer_fraction * target_count))
        target_start = max(0, min(target_start, self._total_frames - target_count))
        self.set_visible_range(target_start, target_start + target_count - 1)
        event.accept()

    def _frame_boundary_x(self, frame_boundary: int, track: QRectF) -> float:
        """Map an inclusive-range boundary to the drawable track."""
        visible_count = self._visible_end - self._visible_start + 1
        fraction = (frame_boundary - self._visible_start) / visible_count
        return track.left() + max(0.0, min(fraction, 1.0)) * track.width()

    def _find_overlap_indices(
        self, possessions: Sequence[Possession]
    ) -> Set[int]:
        """Return source indices of every possession participating in an overlap."""
        ordered: List[Tuple[int, Possession]] = sorted(
            enumerate(possessions), key=lambda pair: pair[1].start_frame
        )
        overlaps: Set[int] = set()
        for position, (left_index, left) in enumerate(ordered):
            for right_index, right in ordered[position + 1 :]:
                if right.start_frame > left.end_frame:
                    break
                overlaps.add(left_index)
                overlaps.add(right_index)
        return overlaps

    def _follow_current_into_view(self) -> None:
        """Recenter the existing span only after current frame leaves the view."""
        if (
            self._current_frame is None
            or self._total_frames <= 0
            or self._visible_start <= self._current_frame <= self._visible_end
        ):
            return
        visible_count = self._visible_end - self._visible_start + 1
        start_frame = self._current_frame - visible_count // 2
        start_frame = max(
            0,
            min(start_frame, self._total_frames - visible_count),
        )
        self._visible_start = start_frame
        self._visible_end = start_frame + visible_count - 1
