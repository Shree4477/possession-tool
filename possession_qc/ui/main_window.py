"""Main application window for the native-libmpv technical spike."""

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from possession_qc.domain import (
    InteractionMode,
    InteractionState,
    Possession,
    PossessionEditError,
    PossessionEditResult,
    PossessionEditor,
    resolve_interaction_state,
)
from possession_qc.frame_index import (
    FfprobeFrameIndexProvider,
    FrameIndex,
    FrameIndexCache,
    FrameIndexResult,
    FrameIndexService,
)
from possession_qc.mapping import (
    MappingDocument,
    MappingRepository,
    PossessionMappingCodec,
)
from possession_qc.player.base import VideoPlayer
from possession_qc.player.mpv_native import NativeMpvPlayer
from possession_qc.timecode import format_timestamp
from possession_qc.ui.frame_index_worker import FrameIndexWorker
from possession_qc.ui.timeline import PossessionTimeline


class MainWindow(QMainWindow):
    """Provide the initial application shell and native libmpv controls."""

    presentation_time_changed = Signal(float)

    def __init__(self) -> None:
        """Build the application shell and schedule native player creation."""
        super().__init__()
        self._player: Optional[VideoPlayer] = None
        self._video_path: Optional[Path] = None
        self._frame_index_service = FrameIndexService(
            FfprobeFrameIndexProvider(), FrameIndexCache()
        )
        self._frame_index_worker: Optional[FrameIndexWorker] = None
        self._frame_index_progress: Optional[QProgressDialog] = None
        self._frame_index_cancel_requested = False
        self._frame_index: Optional[FrameIndex] = None
        self._frame_index_status = "Frame index not loaded"
        self._last_presentation_seconds = 0.0
        self._mapping_repository = MappingRepository(codec=PossessionMappingCodec())
        self._mapping_document: Optional[MappingDocument] = None
        self._possession_editor = PossessionEditor()
        self._current_possession: Optional[Possession] = None
        self._current_possession_index: Optional[int] = None
        self._current_frame: Optional[int] = None
        self._new_possession_start_frame: Optional[int] = None
        self._suspended_possession_index: Optional[int] = None
        self._selected_boundary: Optional[str] = None
        self._suppress_selection_seek = False
        self._shortcuts: List[QShortcut] = []
        self._current_time = QLabel("Current frame —  ·  00:00.000")
        self._video_surface = self._create_video_surface()

        self.setWindowTitle("Possession QC Tool")
        self.resize(1366, 768)
        self.setMinimumSize(1024, 640)
        self.setToolBar(self._create_toolbar())
        self.setCentralWidget(self._create_content())
        self.setStatusBar(self._create_status_bar())
        self._install_shortcuts()

        self.presentation_time_changed.connect(self._show_presentation_time)
        QTimer.singleShot(0, self._initialize_player)

    def setToolBar(self, toolbar: QToolBar) -> None:
        """Attach the primary toolbar to the top toolbar area."""
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Release libmpv before Qt destroys its native parent window."""
        if not self._confirm_unsaved_mapping():
            event.ignore()
            return
        if self._frame_index_worker is not None and self._frame_index_worker.isRunning():
            self._frame_index_worker.cancel()
            if not self._frame_index_worker.wait(5000):
                QMessageBox.warning(
                    self,
                    "Frame indexing is stopping",
                    "Please close the application again after frame indexing stops.",
                )
                event.ignore()
                return
        if self._player is not None:
            self._player.close()
            self._player = None
        event.accept()

    def _create_toolbar(self) -> QToolBar:
        """Create the deliberately minimal primary toolbar."""
        toolbar = QToolBar("Primary")
        toolbar.setMovable(False)

        open_menu = QMenu(self)
        open_video_action = QAction("Open video", self)
        open_video_action.triggered.connect(self._open_video)
        open_menu.addAction(open_video_action)
        open_json_action = QAction("Open JSON", self)
        open_json_action.triggered.connect(self._open_json)
        open_menu.addAction(open_json_action)

        open_button = QToolButton()
        open_button.setText("Open")
        open_button.setMenu(open_menu)
        open_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(open_button)

        view_button = QToolButton()
        view_button.setText("View")
        view_button.setMenu(self._create_view_menu())
        view_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        toolbar.addWidget(view_button)

        self._save_action = QAction("Save", self)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_action.setEnabled(False)
        self._save_action.triggered.connect(self._save_json)
        toolbar.addAction(self._save_action)
        return toolbar

    def _create_content(self) -> QWidget:
        """Create the resizable three-column application layout."""
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._create_possession_panel())
        splitter.addWidget(self._create_center_panel())
        splitter.addWidget(self._create_action_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([240, 850, 276])
        return splitter

    def _create_view_menu(self) -> QMenu:
        """Create the timeline view dropdown used by the primary toolbar."""
        view_menu = QMenu(self)
        fit_video_action = QAction("Fit complete timeline to video", self)
        fit_video_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_video_action.triggered.connect(self._fit_overview_timeline)
        view_menu.addAction(fit_video_action)

        fit_possession_action = QAction(
            "Fit detail timeline to current possession", self
        )
        fit_possession_action.setShortcut(QKeySequence("Ctrl+1"))
        fit_possession_action.triggered.connect(self._fit_detail_timeline)
        view_menu.addAction(fit_possession_action)

        self._follow_current_frame_action = QAction("Follow current frame", self)
        self._follow_current_frame_action.setCheckable(True)
        self._follow_current_frame_action.setChecked(False)
        self._follow_current_frame_action.toggled.connect(
            self._set_timeline_follow_current_frame
        )
        view_menu.addAction(self._follow_current_frame_action)
        return view_menu

    def _create_possession_panel(self) -> QWidget:
        """Create the placeholder possession-list panel for iteration 2."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        heading = QLabel("POSSESSIONS")
        self._possession_list = QTreeWidget()
        self._possession_list.setHeaderLabels(["#", "Start frame", "End frame"])
        self._possession_list.setStyleSheet(
            "QTreeWidget::item:selected {"
            "background: #2563eb; color: white; font-weight: 700;"
            "}"
        )
        self._possession_list.setEnabled(False)
        self._possession_list.itemSelectionChanged.connect(
            self._select_current_possession
        )
        layout.addWidget(heading)
        layout.addWidget(self._possession_list)
        panel.setMinimumWidth(220)
        return panel

    def _create_center_panel(self) -> QWidget:
        """Create the video surface, playback controls, and timeline placeholders."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._create_video_border(), 1)
        layout.addWidget(self._current_time)
        layout.addLayout(self._create_playback_controls())
        self._overview_timeline = PossessionTimeline("COMPLETE VIDEO", 54)
        self._detail_timeline = PossessionTimeline(
            "CURRENT POSSESSION + BUFFER", 96
        )
        self._overview_timeline.frame_clicked.connect(self._timeline_frame_clicked)
        self._detail_timeline.frame_clicked.connect(self._timeline_frame_clicked)
        self._overview_timeline.fit_requested.connect(self._fit_overview_timeline)
        self._detail_timeline.fit_requested.connect(self._fit_detail_timeline)
        layout.addWidget(self._overview_timeline)
        layout.addWidget(self._detail_timeline)
        return panel

    def _create_video_border(self) -> QFrame:
        """Wrap the native mpv surface in a state-coloured Qt border."""
        self._video_border = QFrame()
        border_layout = QVBoxLayout(self._video_border)
        border_layout.setContentsMargins(3, 3, 3, 3)
        border_layout.setSpacing(0)
        border_layout.addWidget(self._video_surface)
        self._set_video_border_color(None)
        return self._video_border

    def _create_video_surface(self) -> QWidget:
        """Create the native QWidget whose platform window is owned by libmpv."""
        surface = QWidget()
        surface.setAttribute(Qt.WidgetAttribute.WA_DontCreateNativeAncestors)
        surface.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        surface.setAutoFillBackground(True)
        surface.setStyleSheet("background: #111111;")
        surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        surface.setMinimumHeight(280)
        return surface

    def _create_playback_controls(self) -> QHBoxLayout:
        """Create minimal controls for verifying libmpv playback behaviour."""
        controls = QHBoxLayout()
        previous_second = QPushButton("−1 second")
        play_pause = QPushButton("Play / Pause")
        next_second = QPushButton("+1 second")
        previous_frame = QPushButton("−1 frame")
        next_frame = QPushButton("+1 frame")

        previous_second.clicked.connect(self._seek_previous_second)
        play_pause.clicked.connect(self._toggle_playback)
        next_second.clicked.connect(self._seek_next_second)
        previous_frame.clicked.connect(self._step_backward)
        next_frame.clicked.connect(self._step_forward)

        controls.addStretch(1)
        controls.addWidget(previous_second)
        controls.addWidget(play_pause)
        controls.addWidget(next_second)
        controls.addSpacing(16)
        controls.addWidget(previous_frame)
        controls.addWidget(next_frame)
        controls.addStretch(1)
        return controls

    def _create_action_panel(self) -> QWidget:
        """Create the current-possession status and primary edit actions."""
        panel = QWidget()
        self._action_panel = panel
        layout = QVBoxLayout(panel)
        self._active_possession_badge = QLabel("NO ACTIVE POSSESSION")
        self._active_possession_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_active_possession_visual(False)
        self._current_possession_heading = QLabel("CURRENT POSSESSION")
        self._current_possession_details = QLabel("No possession selected")
        self._new_possession_status = QLabel("New possession start: not set")
        layout.addWidget(self._active_possession_badge)
        layout.addWidget(self._current_possession_heading)
        layout.addWidget(self._current_possession_details)
        layout.addSpacing(12)
        layout.addWidget(self._new_possession_status)

        self._new_possession_button = QPushButton("Start a new possession")
        self._new_possession_button.setToolTip(
            "Start a new possession at the current frame (N)"
        )
        self._new_possession_button.clicked.connect(self._toggle_new_possession)
        layout.addWidget(self._new_possession_button)

        self._split_button = QPushButton("Split")
        self._split_button.setToolTip(
            "Split the active possession at the current frame (S)"
        )
        self._split_button.clicked.connect(self._split_current_possession)
        layout.addWidget(self._split_button)

        self._join_next_button = QPushButton("Join")
        self._join_next_button.setToolTip(
            "Join the active possession with the next possession (J)"
        )
        self._join_next_button.clicked.connect(self._join_next_possession)
        layout.addWidget(self._join_next_button)

        self._set_start_button = QPushButton("Move active possession start here")
        self._set_start_button.setToolTip(
            "Move the active possession start to the current frame ([)"
        )
        self._set_start_button.clicked.connect(self._set_possession_start)
        layout.addWidget(self._set_start_button)

        self._set_end_button = QPushButton("Move active possession end here")
        self._set_end_button.setToolTip(
            "Move the active possession end to the current frame (])"
        )
        self._set_end_button.clicked.connect(self._set_possession_end)
        layout.addWidget(self._set_end_button)

        self._delete_button = QPushButton("Delete active possession")
        self._delete_button.setToolTip("Shortcut: Delete")
        self._delete_button.clicked.connect(self._delete_possession)
        layout.addWidget(self._delete_button)
        layout.addSpacing(10)
        layout.addWidget(self._create_shortcut_reference())
        layout.addStretch(1)
        panel.setMinimumWidth(260)
        self._refresh_edit_actions()
        return panel

    def _create_shortcut_reference(self) -> QWidget:
        """Create a compact, glanceable shortcut reference below edit actions."""
        reference = QWidget()
        layout = QVBoxLayout(reference)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        heading = QLabel("KEYBOARD SHORTCUTS")
        heading.setStyleSheet("font-weight: 700; color: #334155;")
        shortcuts = QLabel(
            "Space    Play / pause\n"
            "← / →    Previous / next frame\n"
            "Shift+← / →    Previous / next second\n"
            "Ctrl+← / →    Previous / next minute\n"
            "↑ / ↓    Previous / next possession\n"
            "N    Start / end new possession\n"
            "S    Split\n"
            "J / Shift+J    Join next / previous\n"
            "[ / ]    Move start / end here\n"
            "Delete    Delete active possession\n"
            "Home / End    Go to possession start / end\n"
            "Escape    Cancel / clear selection"
        )
        shortcuts.setStyleSheet("font-size: 14px; color: #475569;")
        shortcuts.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(shortcuts)
        return reference

    def _create_status_bar(self) -> QStatusBar:
        """Create a compact file and runtime-status surface."""
        status_bar = QStatusBar()
        status_bar.showMessage("No video or JSON loaded")
        return status_bar

    def _install_shortcuts(self) -> None:
        """Install playback, selection, and possession-editing shortcuts."""
        shortcuts = (
            ("Space", self._toggle_playback),
            ("Left", self._step_backward),
            ("Right", self._step_forward),
            ("Shift+Left", self._seek_previous_second),
            ("Shift+Right", self._seek_next_second),
            ("Ctrl+Left", self._seek_previous_minute),
            ("Ctrl+Right", self._seek_next_minute),
            ("Up", lambda: self._select_relative_possession(-1)),
            ("Down", lambda: self._select_relative_possession(1)),
            ("Return", self._select_possession_at_current_frame),
            ("Escape", self._cancel_or_clear),
            ("Home", self._seek_possession_start),
            ("End", self._seek_possession_end),
            ("N", self._toggle_new_possession),
            ("Delete", self._delete_possession),
            ("S", self._split_current_possession),
            ("J", self._join_next_possession),
            ("Shift+J", self._join_previous_possession),
            ("[", self._set_possession_start),
            ("]", self._set_possession_end),
        )
        for sequence, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def _initialize_player(self) -> None:
        """Create libmpv after Qt has created the native video surface."""
        try:
            self._player = NativeMpvPlayer(
                int(self._video_surface.winId()), self.presentation_time_changed.emit
            )
        except Exception as error:
            self._player = None
            self.statusBar().showMessage("libmpv initialization failed")
            QMessageBox.critical(
                self,
                "libmpv unavailable",
                "Could not initialize native video playback.\n\n%s" % error,
            )

    def _open_video(self) -> None:
        """Prompt for a local video and load it into the configured backend."""
        if self._player is None:
            QMessageBox.warning(self, "Video unavailable", "libmpv is not initialized.")
            return
        if self._frame_index_worker is not None and self._frame_index_worker.isRunning():
            QMessageBox.information(
                self,
                "Frame indexing in progress",
                "Wait for the current frame index to finish before opening another video.",
            )
            return

        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open match video",
            "",
            "Videos (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)",
        )
        if not filename:
            return
        if not self._confirm_unsaved_mapping():
            return

        self._video_path = Path(filename)
        self._load_mapping_for_video()
        self._frame_index = None
        self._current_frame = None
        self._new_possession_start_frame = None
        self._suspended_possession_index = None
        self._frame_index_status = "Indexing frames…"
        self._current_time.setText("Current frame indexing…  ·  00:00.000")
        self._player.load(self._video_path)
        self._start_frame_index()
        self._refresh_document_state()

    def _load_mapping_for_video(self) -> None:
        """Load a video's adjacent mapping or create an in-memory empty mapping."""
        if self._video_path is None:
            return
        mapping_path = self._video_path.with_suffix(".json")
        try:
            if mapping_path.exists():
                self._mapping_document = self._mapping_repository.load(mapping_path)
            else:
                self._mapping_document = self._mapping_repository.new_document(
                    mapping_path, []
                )
        except (OSError, ValueError) as error:
            self._mapping_document = None
            QMessageBox.warning(
                self,
                "Could not auto-load JSON",
                "The adjacent mapping file could not be loaded. "
                "Use Open JSON to choose an annotation file.\n\n%s" % error,
            )
        self._new_possession_start_frame = None
        self._suspended_possession_index = None
        self._selected_boundary = None
        self._current_possession = None
        self._current_possession_index = None
        self._refresh_possession_list()

    def _start_frame_index(self) -> None:
        """Resolve the current video's exact frame index on a worker thread."""
        if self._video_path is None:
            return
        progress = QProgressDialog(
            "Preparing exact frame numbers for %s…" % self._video_path.name,
            "Cancel",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Indexing video frames")
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setMinimumDuration(0)
        progress.canceled.connect(self._cancel_frame_index)
        self._frame_index_progress = progress
        self._frame_index_cancel_requested = False

        worker = FrameIndexWorker(self._frame_index_service, self._video_path)
        worker.progress.connect(self._frame_index_progressed)
        worker.completed.connect(self._frame_index_completed)
        worker.failed.connect(self._frame_index_failed)
        worker.finished.connect(self._frame_index_finished)
        self._frame_index_worker = worker
        worker.start()
        progress.show()

    def _frame_index_progressed(
        self, processed_seconds: float, total_seconds: float
    ) -> None:
        """Show decoded presentation-time progress without estimating frames."""
        if self._frame_index_progress is None:
            return
        maximum = 1000
        self._frame_index_progress.setRange(0, maximum)
        value = int(
            max(0.0, min(processed_seconds / total_seconds, 1.0)) * maximum
        )
        self._frame_index_progress.setValue(value)
        self._frame_index_progress.setLabelText(
            "Preparing exact frame numbers…\nProcessed %s / %s"
            % (
                format_timestamp(processed_seconds),
                format_timestamp(total_seconds),
            )
        )

    def _cancel_frame_index(self) -> None:
        """Cancel an active frame-index build from its modal progress dialog."""
        if self._frame_index_worker is None or not self._frame_index_worker.isRunning():
            return
        self._frame_index_cancel_requested = True
        self._frame_index_status = "Cancelling frame index…"
        if self._frame_index_progress is not None:
            self._frame_index_progress.setLabelText("Cancelling frame indexing…")
            self._frame_index_progress.setCancelButton(None)
            self._frame_index_progress.show()
        self._frame_index_worker.cancel()
        self._refresh_document_state()

    def _frame_index_completed(self, result: FrameIndexResult) -> None:
        """Activate a resolved index and refresh exact current-frame display."""
        self._close_frame_index_progress()
        self._frame_index = result.frame_index
        source = "cache" if result.from_cache else "ffprobe"
        self._frame_index_status = "Frame index ready (%s, %d frames)" % (
            source,
            self._frame_index.frame_count,
        )
        if result.cache_warning:
            self._frame_index_status = "%s; cache unavailable" % self._frame_index_status
        self._show_presentation_time(self._last_presentation_seconds)
        if self._current_possession is not None:
            self._seek_to_frame(self._current_possession.start_frame)
        self._refresh_document_state()

    def _frame_index_failed(self, message: str) -> None:
        """Keep playback available while reporting an unusable exact index."""
        self._close_frame_index_progress()
        self._frame_index = None
        self._frame_index_status = "Frame index failed: %s" % message
        self._show_presentation_time(self._last_presentation_seconds)
        self._refresh_document_state()
        QMessageBox.warning(
            self,
            "Exact frame indexing failed",
            "Video playback remains available, but exact frame editing is disabled.\n\n%s"
            % message,
        )

    def _frame_index_finished(self) -> None:
        """Release the completed one-shot worker object."""
        was_cancelled = self._frame_index_cancel_requested
        self._close_frame_index_progress()
        if self._frame_index_worker is not None:
            self._frame_index_worker.deleteLater()
            self._frame_index_worker = None
        if was_cancelled:
            self._frame_index_cancel_requested = False
            self._frame_index_status = "Frame index cancelled"
            self._show_presentation_time(self._last_presentation_seconds)
            self._refresh_document_state()

    def _close_frame_index_progress(self) -> None:
        """Close and release the current modal frame-index progress dialog."""
        if self._frame_index_progress is None:
            return
        self._frame_index_progress.canceled.disconnect(self._cancel_frame_index)
        self._frame_index_progress.close()
        self._frame_index_progress.deleteLater()
        self._frame_index_progress = None

    def _open_json(self) -> None:
        """Prompt for and load a schema-neutral possession mapping JSON file."""
        filename, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open possession mapping",
            str(self._video_path.parent) if self._video_path is not None else "",
            "JSON files (*.json);;All files (*)",
        )
        if not filename:
            return
        if not self._confirm_unsaved_mapping():
            return

        try:
            self._mapping_document = self._mapping_repository.load(Path(filename))
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Could not open JSON",
                "The mapping file could not be loaded.\n\n%s" % error,
            )
            return
        self._new_possession_start_frame = None
        self._suspended_possession_index = None
        self._selected_boundary = None
        self._current_possession = None
        self._current_possession_index = None
        self._refresh_possession_list()
        self._refresh_document_state()

    def _refresh_possession_list(
        self, selected_index: Optional[int] = None
    ) -> None:
        """Render possessions and optionally retain an edit-driven selection."""
        self._suppress_selection_seek = True
        self._possession_list.clear()
        if self._mapping_document is None:
            self._possession_list.setEnabled(False)
            self._suppress_selection_seek = False
            self._refresh_current_possession_details()
            self._refresh_edit_actions()
            self._refresh_timelines()
            return

        for index, possession in enumerate(self._mapping_document.data):
            if not isinstance(possession, Possession):
                continue
            item = QTreeWidgetItem(
                [
                    str(possession.possession_num),
                    str(possession.start_frame),
                    str(possession.end_frame),
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, index)
            self._possession_list.addTopLevelItem(item)
        self._possession_list.setEnabled(True)
        if selected_index is not None:
            selected_item = self._possession_list.topLevelItem(selected_index)
            if selected_item is not None:
                self._possession_list.setCurrentItem(selected_item)
        self._suppress_selection_seek = False
        self._refresh_current_possession_details()
        self._refresh_edit_actions()
        self._refresh_timelines()

    def _select_current_possession(self) -> None:
        """Make the explicitly selected list item the current possession."""
        selected_items = self._possession_list.selectedItems()
        if not selected_items or self._mapping_document is None:
            self._current_possession = None
            self._current_possession_index = None
            self._selected_boundary = None
            self._refresh_current_possession_details()
            self._refresh_edit_actions()
            self._refresh_timelines()
            return

        index = selected_items[0].data(0, Qt.ItemDataRole.UserRole)
        possession = self._mapping_document.data[int(index)]
        if not isinstance(possession, Possession):
            return
        self._current_possession = possession
        self._current_possession_index = int(index)
        self._selected_boundary = None
        self._refresh_current_possession_details()
        self._refresh_edit_actions()
        self._refresh_timelines()
        self._fit_detail_timeline()
        if not self._suppress_selection_seek:
            self._seek_to_frame(possession.start_frame)

    def _refresh_current_possession_details(self) -> None:
        """Render current-possession and pending-creation status."""
        self._refresh_active_possession_visual()
        state = self._interaction_state()
        if state.mode == InteractionMode.NO_POSSESSION:
            self._new_possession_status.setVisible(False)
            self._new_possession_button.setText("Start a new possession")
            self._new_possession_button.setToolTip(
                "Start a new possession at the current frame (N)"
            )
        elif state.mode == InteractionMode.NEW_POSSESSION:
            self._new_possession_status.setVisible(True)
            self._new_possession_status.setText(
                "New possession start: frame %d" % self._new_possession_start_frame
            )
            self._new_possession_button.setText("End current possession")
            self._new_possession_button.setToolTip(
                "End the new possession at the current frame (N); Escape cancels"
            )
        else:
            self._new_possession_status.setVisible(False)
            self._new_possession_button.setText("Possession active")
            self._new_possession_button.setToolTip(
                "Move to a gap before starting a new possession"
            )
        if self._current_possession is None:
            self._current_possession_heading.setText("CURRENT POSSESSION")
            self._current_possession_details.setText("No possession selected")
            return

        possession = self._current_possession
        self._current_possession_heading.setText(
            "CURRENT POSSESSION %d" % possession.possession_num
        )
        boundary_text = ""
        if self._selected_boundary is not None:
            boundary_text = "\nSelected boundary: possession %s" % self._selected_boundary
        self._current_possession_details.setText(
            "Possession start\n"
            "Frame %d  ·  %s\n\n"
            "Possession end\n"
            "Frame %d  ·  %s\n\n"
            "Duration: %d frames%s"
            % (
                possession.start_frame,
                format_timestamp(possession.start_time),
                possession.end_frame,
                format_timestamp(possession.end_time),
                possession.duration_frames,
                boundary_text,
            )
        )

    def _refresh_active_possession_visual(self) -> None:
        """Show the possession containing current frame and hide it in gaps."""
        state = self._interaction_state()
        if state.mode == InteractionMode.NEW_POSSESSION:
            self._show_status_badge("CREATING NEW POSSESSION", "#16a34a")
            self._set_video_border_color("#16a34a")
            return
        if (
            state.mode == InteractionMode.ACTIVE_POSSESSION
            and state.active_index is not None
        ):
            possession = self._possessions()[state.active_index]
            self._set_active_possession_visual(True, possession.possession_num)
            return
        self._set_active_possession_visual(False)

    def _interaction_state(self) -> InteractionState:
        """Return the state derived from current frame and pending creation."""
        return resolve_interaction_state(
            self._possessions(),
            self._current_frame,
            self._new_possession_start_frame,
        )

    def _synchronize_interaction_selection(self) -> None:
        """Switch selection on possession entry while retaining it through gaps."""
        state = self._interaction_state()
        if state.mode == InteractionMode.NEW_POSSESSION:
            if self._current_possession_index is not None:
                self._set_possession_list_selection(None)
            return
        if (
            state.mode == InteractionMode.ACTIVE_POSSESSION
            and state.active_index != self._current_possession_index
        ):
            self._set_possession_list_selection(state.active_index)

    def _set_possession_list_selection(self, index: Optional[int]) -> None:
        """Set list selection without causing an automatic seek."""
        self._suppress_selection_seek = True
        try:
            if index is None:
                self._possession_list.clearSelection()
                self._possession_list.setCurrentItem(None)
                return
            item = self._possession_list.topLevelItem(index)
            if item is not None:
                self._possession_list.setCurrentItem(item)
        finally:
            self._suppress_selection_seek = False

    def _set_active_possession_visual(
        self, active: bool, possession_num: Optional[int] = None
    ) -> None:
        """Show a strong, compact active-possession state in the action panel."""
        if active and possession_num is not None:
            self._show_status_badge("ACTIVE POSSESSION %d" % possession_num, "#2563eb")
            self._set_video_border_color("#2563eb")
            return
        self._active_possession_badge.setVisible(False)
        self._set_video_border_color(None)

    def _show_status_badge(self, text: str, color: str) -> None:
        """Show a high-contrast interaction-state message in the action panel."""
        self._active_possession_badge.setVisible(True)
        self._active_possession_badge.setText(text)
        self._active_possession_badge.setStyleSheet(
            "background: %s; color: white; font-weight: 700;"
            "padding: 7px; border-radius: 3px;" % color
        )

    def _set_video_border_color(self, color: Optional[str]) -> None:
        """Apply a possession-state border without styling the native mpv widget."""
        border_color = "transparent" if color is None else color
        self._video_border.setStyleSheet(
            "QFrame { background: #111111; border: 3px solid %s; }" % border_color
        )

    def _refresh_edit_actions(self) -> None:
        """Enable only edit actions valid for the current UI state."""
        if not hasattr(self, "_new_possession_button"):
            return
        has_document = self._mapping_document is not None
        has_frame = self._frame_index is not None and self._current_frame is not None
        ready = has_document and has_frame
        selected = self._current_possession
        selected_index = self._current_possession_index
        state = self._interaction_state()
        can_toggle_new = state.mode == InteractionMode.NO_POSSESSION
        if state.mode == InteractionMode.NEW_POSSESSION:
            can_toggle_new = self._can_end_new_possession()
        self._new_possession_button.setEnabled(ready and can_toggle_new)
        can_split = (
            ready
            and selected is not None
            and selected.start_frame < self._current_frame <= selected.end_frame
        )
        self._split_button.setEnabled(can_split)
        self._join_next_button.setEnabled(
            ready
            and selected_index is not None
            and selected_index + 1 < len(self._possessions())
        )
        self._set_start_button.setEnabled(
            ready and selected is not None and self._current_frame <= selected.end_frame
        )
        self._set_end_button.setEnabled(
            ready and selected is not None and self._current_frame >= selected.start_frame
        )
        self._delete_button.setEnabled(has_document and selected is not None)

    def _can_end_new_possession(self) -> bool:
        """Return whether the pending inclusive range is ordered and overlap-free."""
        if self._new_possession_start_frame is None or self._current_frame is None:
            return False
        if self._current_frame < self._new_possession_start_frame:
            return False
        return not any(
            self._new_possession_start_frame <= possession.end_frame
            and self._current_frame >= possession.start_frame
            for possession in self._possessions()
        )

    def _possessions(self) -> List[Possession]:
        """Return the typed possession list from the current document."""
        if self._mapping_document is None:
            return []
        return [
            item
            for item in self._mapping_document.data
            if isinstance(item, Possession)
        ]

    def _timestamp_for_frame(self, frame_number: int) -> float:
        """Resolve a frame timestamp from the authoritative exact index."""
        if self._frame_index is None:
            raise PossessionEditError("Exact frame indexing is not ready.")
        try:
            return self._frame_index.timestamp_seconds(frame_number)
        except (IndexError, TypeError) as error:
            raise PossessionEditError(
                "Frame %d is outside the indexed video." % frame_number
            ) from error

    def _apply_possession_edit(self, result: PossessionEditResult) -> None:
        """Apply an editor result, mark it dirty, and refresh selection safely."""
        if self._mapping_document is None:
            return
        self._mapping_document.data = result.possessions
        self._mapping_document.mark_dirty()
        self._current_possession = None
        self._current_possession_index = None
        self._selected_boundary = None
        self._refresh_possession_list(result.selected_index)
        self._refresh_document_state()

    def _run_possession_edit(
        self, edit: Callable[[], PossessionEditResult]
    ) -> bool:
        """Run one domain edit and present a concise validation warning."""
        try:
            result = edit()
        except PossessionEditError as error:
            QMessageBox.warning(self, "Possession not changed", str(error))
            return False
        self._apply_possession_edit(result)
        return True

    def _set_new_possession_start(self) -> None:
        """Remember the current frame as the start of a new possession."""
        if (
            self._mapping_document is None
            or self._current_frame is None
            or self._interaction_state().mode != InteractionMode.NO_POSSESSION
        ):
            return
        self._suspended_possession_index = self._current_possession_index
        self._new_possession_start_frame = self._current_frame
        self._set_possession_list_selection(None)
        self._refresh_current_possession_details()
        self._refresh_edit_actions()

    def _toggle_new_possession(self) -> None:
        """Start or end a new possession according to the current creation state."""
        state = self._interaction_state()
        if state.mode == InteractionMode.NO_POSSESSION:
            self._set_new_possession_start()
            return
        if state.mode == InteractionMode.NEW_POSSESSION and self._can_end_new_possession():
            self._create_possession()

    def _create_possession(self) -> None:
        """Create a possession from the pending start through current frame."""
        if (
            self._mapping_document is None
            or self._new_possession_start_frame is None
            or self._current_frame is None
            or self._frame_index is None
        ):
            return
        start_frame = self._new_possession_start_frame
        end_frame = self._current_frame
        if self._run_possession_edit(
            lambda: self._possession_editor.create(
                self._possessions(),
                start_frame,
                end_frame,
                self._timestamp_for_frame,
            )
        ):
            self._new_possession_start_frame = None
            self._suspended_possession_index = None
            self._refresh_current_possession_details()
            self._refresh_edit_actions()

    def _delete_possession(self) -> None:
        """Confirm and delete the explicitly selected current possession."""
        if self._current_possession_index is None:
            return
        choice = QMessageBox.question(
            self,
            "Delete possession",
            "Delete current possession %d?" % self._current_possession.possession_num,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        selected_index = self._current_possession_index
        self._run_possession_edit(
            lambda: self._possession_editor.delete(
                self._possessions(), selected_index
            )
        )

    def _split_current_possession(self) -> None:
        """Split the current possession before the current frame."""
        if self._current_possession_index is None or self._current_frame is None:
            return
        selected_index = self._current_possession_index
        current_frame = self._current_frame
        self._run_possession_edit(
            lambda: self._possession_editor.split(
                self._possessions(),
                selected_index,
                current_frame,
                self._timestamp_for_frame,
            )
        )

    def _join_next_possession(self) -> None:
        """Join the current possession with its next list neighbour."""
        if self._current_possession_index is None or self._frame_index is None:
            return
        selected_index = self._current_possession_index
        self._run_possession_edit(
            lambda: self._possession_editor.join_next(
                self._possessions(), selected_index, self._timestamp_for_frame
            )
        )

    def _join_previous_possession(self) -> None:
        """Join the current possession with its previous list neighbour."""
        if self._current_possession_index is None or self._frame_index is None:
            return
        selected_index = self._current_possession_index
        self._run_possession_edit(
            lambda: self._possession_editor.join_previous(
                self._possessions(), selected_index, self._timestamp_for_frame
            )
        )

    def _set_possession_start(self) -> None:
        """Set current possession start to the exact current frame."""
        if self._current_possession_index is None or self._current_frame is None:
            return
        selected_index = self._current_possession_index
        frame_number = self._current_frame
        self._run_possession_edit(
            lambda: self._possession_editor.set_start(
                self._possessions(),
                selected_index,
                frame_number,
                self._timestamp_for_frame,
            )
        )

    def _set_possession_end(self) -> None:
        """Set current possession end to the exact current frame."""
        if self._current_possession_index is None or self._current_frame is None:
            return
        selected_index = self._current_possession_index
        frame_number = self._current_frame
        self._run_possession_edit(
            lambda: self._possession_editor.set_end(
                self._possessions(),
                selected_index,
                frame_number,
                self._timestamp_for_frame,
            )
        )

    def _select_relative_possession(self, offset: int) -> None:
        """Select the previous or next possession and seek to its start."""
        count = self._possession_list.topLevelItemCount()
        if count == 0:
            return
        if self._current_possession_index is None:
            target = 0 if offset > 0 else count - 1
        else:
            target = max(0, min(self._current_possession_index + offset, count - 1))
        self._possession_list.setCurrentItem(
            self._possession_list.topLevelItem(target)
        )

    def _select_possession_at_current_frame(self) -> None:
        """Select the possession containing current frame or clear on a gap."""
        if self._current_frame is None:
            return
        for index, possession in enumerate(self._possessions()):
            if possession.start_frame <= self._current_frame <= possession.end_frame:
                self._possession_list.setCurrentItem(
                    self._possession_list.topLevelItem(index)
                )
                return
        self._clear_possession_selection()

    def _clear_possession_selection(self) -> None:
        """Clear explicit possession selection without changing creation state."""
        self._possession_list.clearSelection()
        self._possession_list.setCurrentItem(None)
        self._refresh_current_possession_details()
        self._refresh_edit_actions()
        self._refresh_timelines()
        self._fit_detail_timeline()

    def _cancel_or_clear(self) -> None:
        """Cancel pending creation, otherwise clear possession selection."""
        if self._new_possession_start_frame is not None:
            self._new_possession_start_frame = None
            suspended_index = self._suspended_possession_index
            self._suspended_possession_index = None
            state = self._interaction_state()
            if state.mode == InteractionMode.ACTIVE_POSSESSION:
                self._set_possession_list_selection(state.active_index)
            elif suspended_index is not None:
                self._set_possession_list_selection(suspended_index)
            self._refresh_current_possession_details()
            self._refresh_edit_actions()
            return
        self._clear_possession_selection()
        self._synchronize_interaction_selection()

    def _timeline_frame_clicked(self, frame_number: int) -> None:
        """Seek to a clicked frame and select its possession, clearing on gaps."""
        containing_index = None
        for index, possession in enumerate(self._possessions()):
            if possession.start_frame <= frame_number <= possession.end_frame:
                containing_index = index
                break
        if containing_index is None:
            self._clear_possession_selection()
        else:
            self._suppress_selection_seek = True
            self._possession_list.setCurrentItem(
                self._possession_list.topLevelItem(containing_index)
            )
            self._suppress_selection_seek = False
        self._seek_to_frame(frame_number)

    def _refresh_timelines(self) -> None:
        """Push current frame, selection, and exact visible ranges to timelines."""
        if not hasattr(self, "_overview_timeline"):
            return
        total_frames = self._frame_index.frame_count if self._frame_index else 0
        possessions = self._possessions()
        self._overview_timeline.set_state(
            possessions,
            self._current_frame,
            self._current_possession_index,
            total_frames,
        )
        detail_start, detail_end = self._detail_timeline_range(total_frames)
        self._detail_timeline.set_state(
            possessions,
            self._current_frame,
            self._current_possession_index,
            total_frames,
            detail_start,
            detail_end,
            self._new_possession_start_frame,
        )
        if self._interaction_state().mode == InteractionMode.NEW_POSSESSION:
            self._detail_timeline.set_visible_range(detail_start, detail_end)

    def _detail_timeline_range(self, total_frames: int) -> Tuple[int, int]:
        """Return a five-second presentation-time buffer around current context."""
        if self._frame_index is None or total_frames <= 0:
            return 0, 0
        if (
            self._interaction_state().mode == InteractionMode.NEW_POSSESSION
            and self._current_frame is not None
        ):
            start_seconds = self._frame_index.timestamp_seconds(self._current_frame)
            end_seconds = start_seconds
        elif self._current_possession is not None:
            try:
                start_seconds = self._frame_index.timestamp_seconds(
                    self._current_possession.start_frame
                )
                end_seconds = self._frame_index.timestamp_seconds(
                    self._current_possession.end_frame
                )
            except IndexError:
                start_seconds = self._last_presentation_seconds
                end_seconds = self._last_presentation_seconds
        else:
            start_seconds = self._last_presentation_seconds
            end_seconds = self._last_presentation_seconds
        visible_start = self._frame_index.frame_for_seconds(
            max(0.0, start_seconds - 5.0)
        )
        visible_end = self._frame_index.frame_for_seconds(end_seconds + 5.0)
        return visible_start, visible_end

    def _fit_overview_timeline(self) -> None:
        """Fit the complete indexed video into the overview timeline."""
        if hasattr(self, "_overview_timeline"):
            self._overview_timeline.fit_video()

    def _fit_detail_timeline(self) -> None:
        """Fit selected possession plus buffer, or current-frame context."""
        if not hasattr(self, "_detail_timeline"):
            return
        total_frames = self._frame_index.frame_count if self._frame_index else 0
        start_frame, end_frame = self._detail_timeline_range(total_frames)
        self._detail_timeline.set_visible_range(start_frame, end_frame)

    def _set_timeline_follow_current_frame(self, enabled: bool) -> None:
        """Apply optional follow-current-frame behavior to both timelines."""
        if not hasattr(self, "_overview_timeline"):
            return
        self._overview_timeline.set_follow_current_frame(enabled)
        self._detail_timeline.set_follow_current_frame(enabled)

    def _seek_possession_start(self) -> None:
        """Seek to the current possession's inclusive start frame."""
        if self._current_possession is not None:
            self._seek_to_frame(self._current_possession.start_frame)

    def _seek_possession_end(self) -> None:
        """Seek to the current possession's inclusive end frame."""
        if self._current_possession is not None:
            self._seek_to_frame(self._current_possession.end_frame)

    def _select_boundary(self, boundary: str) -> None:
        """Choose the start or end boundary for keyboard nudging."""
        if self._current_possession is None or boundary not in ("start", "end"):
            return
        self._selected_boundary = boundary
        self._refresh_current_possession_details()

    def _nudge_selected_boundary(self, frame_delta: int) -> None:
        """Move the selected possession boundary by an exact frame delta."""
        if self._current_possession is None or self._current_possession_index is None:
            return
        selected_index = self._current_possession_index
        boundary = self._selected_boundary
        if boundary == "start":
            frame_number = self._current_possession.start_frame + frame_delta
            changed = self._run_possession_edit(
                lambda: self._possession_editor.set_start(
                    self._possessions(),
                    selected_index,
                    frame_number,
                    self._timestamp_for_frame,
                )
            )
            if changed:
                self._selected_boundary = "start"
                self._refresh_current_possession_details()
        elif boundary == "end":
            frame_number = self._current_possession.end_frame + frame_delta
            changed = self._run_possession_edit(
                lambda: self._possession_editor.set_end(
                    self._possessions(),
                    selected_index,
                    frame_number,
                    self._timestamp_for_frame,
                )
            )
            if changed:
                self._selected_boundary = "end"
                self._refresh_current_possession_details()

    def _save_json(self) -> bool:
        """Save the current mapping and report whether the operation succeeded."""
        if self._mapping_document is None:
            return False
        try:
            self._mapping_repository.save(self._mapping_document)
        except (OSError, TypeError, ValueError) as error:
            QMessageBox.critical(
                self,
                "Could not save JSON",
                "The mapping file could not be saved.\n\n%s" % error,
            )
            return False
        self._refresh_document_state()
        return True

    def _confirm_unsaved_mapping(self) -> bool:
        """Ask how to handle unsaved mapping changes before replacement or exit."""
        if self._mapping_document is None or not self._mapping_document.dirty:
            return True

        choice = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes to the possession mapping before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        if choice == QMessageBox.StandardButton.Save:
            return self._save_json()
        return True

    def _refresh_document_state(self) -> None:
        """Refresh title, save availability, and compact file status text."""
        dirty = self._mapping_document is not None and self._mapping_document.dirty
        self._save_action.setEnabled(bool(dirty))
        self.setWindowTitle("%sPossession QC Tool" % ("* " if dirty else ""))

        video_name = self._video_path.name if self._video_path is not None else "None"
        json_name = (
            self._mapping_document.path.name
            if self._mapping_document is not None
            else "None"
        )
        state = "Pending changes" if dirty else "No pending changes"
        self.statusBar().showMessage(
            "Video: %s    JSON: %s    %s    %s"
            % (video_name, json_name, self._frame_index_status, state)
        )

    def _toggle_playback(self) -> None:
        """Toggle playback when a player and video are available."""
        if self._player is not None and self._video_path is not None:
            self._player.toggle_playback()

    def _seek_previous_second(self) -> None:
        """Seek backward by one second."""
        if self._player is not None and self._video_path is not None:
            self._player.seek_relative(-1.0)

    def _seek_next_second(self) -> None:
        """Seek forward by one second."""
        if self._player is not None and self._video_path is not None:
            self._player.seek_relative(1.0)

    def _seek_previous_minute(self) -> None:
        """Seek backward by one minute."""
        if self._player is not None and self._video_path is not None:
            self._player.seek_relative(-60.0)

    def _seek_next_minute(self) -> None:
        """Seek forward by one minute."""
        if self._player is not None and self._video_path is not None:
            self._player.seek_relative(60.0)

    def _step_backward(self) -> None:
        """Move backward by one frame when video is loaded."""
        if self._player is not None and self._video_path is not None:
            self._player.step_backward()

    def _step_forward(self) -> None:
        """Advance by one frame when video is loaded."""
        if self._player is not None and self._video_path is not None:
            self._player.step_forward()

    def _seek_to_frame(self, frame_number: int) -> None:
        """Seek to an exact indexed frame when player and index are ready."""
        if self._player is None or self._frame_index is None:
            return
        try:
            timestamp = self._frame_index.timestamp_seconds(frame_number)
        except (IndexError, TypeError):
            QMessageBox.warning(
                self,
                "Frame outside video",
                "Frame %d is outside the indexed video." % frame_number,
            )
            return
        self._player.seek_absolute(timestamp)

    def _show_presentation_time(self, seconds: float) -> None:
        """Map libmpv presentation time to and display the exact current frame."""
        self._last_presentation_seconds = max(0.0, seconds)
        timestamp = format_timestamp(self._last_presentation_seconds)
        if self._frame_index is None:
            self._current_frame = None
            self._current_time.setText("Current frame —  ·  %s" % timestamp)
            self._refresh_current_possession_details()
            self._refresh_edit_actions()
            self._refresh_timelines()
            return
        frame_number = self._frame_index.frame_for_seconds(
            self._last_presentation_seconds
        )
        self._current_frame = frame_number
        self._synchronize_interaction_selection()
        self._current_time.setText(
            "Current frame %d  ·  %s" % (frame_number, timestamp)
        )
        self._refresh_current_possession_details()
        self._refresh_edit_actions()
        self._refresh_timelines()
