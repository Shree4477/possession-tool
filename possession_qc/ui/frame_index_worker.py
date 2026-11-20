"""Qt worker for non-blocking frame-index resolution."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from possession_qc.frame_index import FrameIndexService


class FrameIndexWorker(QThread):
    """Resolve a frame index without blocking Qt's main event loop."""

    completed = Signal(object)
    failed = Signal(str)
    progress = Signal(float, float)

    def __init__(self, service: FrameIndexService, video_path: Path) -> None:
        """Create a one-shot worker for ``video_path``."""
        super().__init__()
        self._service = service
        self._video_path = video_path

    def run(self) -> None:
        """Resolve the index and emit its result unless cancellation was requested."""
        try:
            result = self._service.get_or_build(
                self._video_path, self._report_progress
            )
        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(self._format_failure(error))
            return
        if not self.isInterruptionRequested():
            self.completed.emit(result)

    def cancel(self) -> None:
        """Request worker interruption and terminate an active provider process."""
        self.requestInterruption()
        self._service.cancel()

    def _report_progress(self, processed_seconds: float, total_seconds: float) -> None:
        """Forward provider progress unless cancellation has been requested."""
        if not self.isInterruptionRequested():
            self.progress.emit(processed_seconds, total_seconds)

    def _format_failure(self, error: Exception) -> str:
        """Return a non-empty diagnostic that retains the exception category."""
        detail = str(error).strip()
        if not detail:
            detail = "no additional diagnostic was provided"
        return "%s: %s" % (error.__class__.__name__, detail)
