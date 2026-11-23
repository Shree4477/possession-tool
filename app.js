/**
 * Possession QC Tool — Complete Web Application
 * Frame-authoritative basketball possession quality control running 100% in-browser.
 */

// ============================================================================
// 1. Domain Models & Formatting
// ============================================================================

class Possession {
  constructor(possessionNum, startFrame, startTime, endFrame, endTime, extraFields = {}) {
    if (!Number.isInteger(possessionNum) || possessionNum < 0) {
      throw new TypeError("possession_num must be a non-negative integer");
    }
    if (!Number.isInteger(startFrame) || !Number.isInteger(endFrame)) {
      throw new TypeError("start_frame and end_frame must be integers");
    }
    if (startFrame < 0 || endFrame < 0) {
      throw new RangeError("possession frames cannot be negative");
    }
    if (endFrame < startFrame) {
      throw new RangeError("possession end_frame cannot precede start_frame");
    }

    this.possession_num = possessionNum;
    this.start_frame = startFrame;
    this.start_time = Number(startTime);
    this.end_frame = endFrame;
    this.end_time = Number(endTime);
    this.extra_fields = { ...extraFields };
  }

  get duration_frames() {
    return this.end_frame - this.start_frame + 1;
  }

  get duration_time() {
    return Math.max(0, this.end_time - this.start_time);
  }

  clone(updates = {}) {
    return new Possession(
      updates.possession_num ?? this.possession_num,
      updates.start_frame ?? this.start_frame,
      updates.start_time ?? this.start_time,
      updates.end_frame ?? this.end_frame,
      updates.end_time ?? this.end_time,
      updates.extra_fields ?? { ...this.extra_fields }
    );
  }

  toJSON() {
    return {
      "possession-num": this.possession_num,
      "start-frame": this.start_frame,
      "start-time": Number(this.start_time.toFixed(4)),
      "end-frame": this.end_frame,
      "end-time": Number(this.end_time.toFixed(4)),
      ...this.extra_fields
    };
  }
}

function formatTimestamp(seconds) {
  if (seconds == null || isNaN(seconds) || seconds < 0) return "00:00.000";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const millis = Math.floor((seconds % 1) * 1000);
  const pad = (n, len = 2) => String(n).padStart(len, "0");
  return `${pad(mins)}:${pad(secs)}.${pad(millis, 3)}`;
}

// ============================================================================
// 2. Possession Editor (Domain Rules)
// ============================================================================

class PossessionEditor {
  overlaps(possessions) {
    const sorted = [...possessions].sort((a, b) => a.start_frame - b.start_frame);
    const overlappingPairs = [];
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i + 1].start_frame <= sorted[i].end_frame) {
        overlappingPairs.push([sorted[i], sorted[i + 1]]);
      }
    }
    return overlappingPairs;
  }

  _finalize(possessions, selectedPossession) {
    const sorted = [...possessions].sort((a, b) => a.start_frame - b.start_frame);
    const conflicts = this.overlaps(sorted);
    if (conflicts.length > 0) {
      const [left, right] = conflicts[0];
      throw new Error(`Possessions #${left.possession_num} and #${right.possession_num} would overlap.`);
    }

    const firstNum = (sorted.length > 0 && sorted[0].possession_num === 0) ? 0 : 1;
    const renumbered = sorted.map((item, idx) => item.clone({ possession_num: firstNum + idx }));

    let selectedIndex = null;
    if (selectedPossession) {
      selectedIndex = renumbered.findIndex(
        item => item.start_frame === selectedPossession.start_frame && item.end_frame === selectedPossession.end_frame
      );
      if (selectedIndex === -1) selectedIndex = null;
    }

    return { possessions: renumbered, selectedIndex };
  }

  create(possessions, startFrame, endFrame, timestampForFrame) {
    if (endFrame < startFrame) {
      throw new Error("Current frame must not precede the new possession start.");
    }
    const firstNum = (possessions.length > 0 && possessions[0].possession_num === 0) ? 0 : 1;
    const created = new Possession(
      firstNum,
      startFrame,
      timestampForFrame(startFrame),
      endFrame,
      timestampForFrame(endFrame)
    );
    return this._finalize([...possessions, created], created);
  }

  delete(possessions, selectedIndex) {
    if (selectedIndex == null || selectedIndex < 0 || selectedIndex >= possessions.length) {
      throw new Error("No current possession is selected.");
    }
    const updated = [...possessions];
    updated.splice(selectedIndex, 1);
    return this._finalize(updated, null);
  }

  split(possessions, selectedIndex, currentFrame, timestampForFrame) {
    if (selectedIndex == null || selectedIndex < 0 || selectedIndex >= possessions.length) {
      throw new Error("No current possession is selected.");
    }
    const selected = possessions[selectedIndex];
    if (currentFrame <= selected.start_frame || currentFrame > selected.end_frame) {
      throw new Error("Current frame must be after the possession start and no later than its end.");
    }

    const left = selected.clone({
      end_frame: currentFrame - 1,
      end_time: timestampForFrame(currentFrame - 1)
    });
    const right = selected.clone({
      start_frame: currentFrame,
      start_time: timestampForFrame(currentFrame)
    });

    const updated = [...possessions];
    updated.splice(selectedIndex, 1, left, right);
    return this._finalize(updated, right);
  }

  joinNext(possessions, selectedIndex, timestampForFrame) {
    if (selectedIndex == null || selectedIndex < 0 || selectedIndex >= possessions.length) {
      throw new Error("No current possession is selected.");
    }
    if (selectedIndex + 1 >= possessions.length) {
      throw new Error("The current possession has no next possession.");
    }

    const selected = possessions[selectedIndex];
    const following = possessions[selectedIndex + 1];
    const joined = selected.clone({
      end_frame: following.end_frame,
      end_time: timestampForFrame(following.end_frame)
    });

    const updated = [...possessions];
    updated.splice(selectedIndex, 2, joined);
    return this._finalize(updated, joined);
  }

  joinPrevious(possessions, selectedIndex, timestampForFrame) {
    if (selectedIndex == null || selectedIndex <= 0 || selectedIndex >= possessions.length) {
      throw new Error("The current possession has no previous possession.");
    }

    const previous = possessions[selectedIndex - 1];
    const selected = possessions[selectedIndex];
    const joined = previous.clone({
      end_frame: selected.end_frame,
      end_time: timestampForFrame(selected.end_frame)
    });

    const updated = [...possessions];
    updated.splice(selectedIndex - 1, 2, joined);
    return this._finalize(updated, joined);
  }

  setStart(possessions, selectedIndex, frameNumber, timestampForFrame) {
    if (selectedIndex == null || selectedIndex < 0 || selectedIndex >= possessions.length) {
      throw new Error("No current possession is selected.");
    }
    const selected = possessions[selectedIndex];
    if (frameNumber > selected.end_frame) {
      throw new Error("Possession start cannot follow possession end.");
    }

    const updated = [...possessions];
    const changed = selected.clone({
      start_frame: frameNumber,
      start_time: timestampForFrame(frameNumber)
    });
    updated[selectedIndex] = changed;
    return this._finalize(updated, changed);
  }

  setEnd(possessions, selectedIndex, frameNumber, timestampForFrame) {
    if (selectedIndex == null || selectedIndex < 0 || selectedIndex >= possessions.length) {
      throw new Error("No current possession is selected.");
    }
    const selected = possessions[selectedIndex];
    if (frameNumber < selected.start_frame) {
      throw new Error("Possession end cannot precede possession start.");
    }

    const updated = [...possessions];
    const changed = selected.clone({
      end_frame: frameNumber,
      end_time: timestampForFrame(frameNumber)
    });
    updated[selectedIndex] = changed;
    return this._finalize(updated, changed);
  }
}

// ============================================================================
// 3. Application State & Orchestrator
// ============================================================================

class App {
  constructor() {
    this.editor = new PossessionEditor();
    this.possessions = [];
    this.selectedIndex = null;
    this.currentFrame = 0;
    this.totalFrames = 0;
    this.fps = 30.0;
    this.videoDuration = 0;
    this.newPossessionStartFrame = null;
    this.followCurrentFrame = false;
    this.isDirty = false;
    this.loadedFileName = "match-video";
    this.isDemoActive = false;

    // View States (Collapsible panels & Theater / Big Video mode)
    this.isTheaterMode = false;
    this.isLeftCollapsed = false;
    this.isRightCollapsed = false;

    // Timeline view windows
    this.detailVisibleStart = 0;
    this.detailVisibleEnd = 0;

    this._initDOMElements();
    this._initTimelines();
    this._attachEventListeners();
    this._updateUI();

    // Resize observer for crisp canvas drawing
    window.addEventListener("resize", () => {
      this.renderOverviewTimeline();
      this.renderDetailTimeline();
    });
  }

  _initDOMElements() {
    this.appLayout = document.getElementById("appLayout");
    this.video = document.getElementById("videoElement");
    this.demoCanvas = document.getElementById("demoCanvas");
    this.videoPlaceholder = document.getElementById("videoPlaceholder");
    this.videoBorder = document.getElementById("videoBorder");
    this.videoDropArea = document.getElementById("videoDropArea");

    // Side Panels & Floating Tabs
    this.possessionPanel = document.getElementById("possessionPanel");
    this.actionPanel = document.getElementById("actionPanel");
    this.toggleLeftPanelBtn = document.getElementById("toggleLeftPanelBtn");
    this.toggleRightPanelBtn = document.getElementById("toggleRightPanelBtn");
    this.expandLeftTab = document.getElementById("expandLeftTab");
    this.expandRightTab = document.getElementById("expandRightTab");

    // Inputs
    this.videoFileInput = document.getElementById("videoFileInput");
    this.jsonFileInput = document.getElementById("jsonFileInput");
    this.fpsSelect = document.getElementById("fpsSelect");
    this.speedSelect = document.getElementById("speedSelect");

    // Readouts
    this.currentReadout = document.getElementById("currentReadout");
    this.currentFpsLabel = document.getElementById("currentFpsLabel");
    this.overviewMeta = document.getElementById("overviewMeta");
    this.statusMessage = document.getElementById("statusMessage");
    this.dirtyIndicator = document.getElementById("dirtyIndicator");
    this.possessionCount = document.getElementById("possessionCount");
    this.possessionListBody = document.getElementById("possessionListBody");

    // Details & Badge
    this.activeBadge = document.getElementById("activeBadge");
    this.detailNum = document.getElementById("detailNum");
    this.detailStartFrame = document.getElementById("detailStartFrame");
    this.detailStartTime = document.getElementById("detailStartTime");
    this.detailEndFrame = document.getElementById("detailEndFrame");
    this.detailEndTime = document.getElementById("detailEndTime");
    this.detailDuration = document.getElementById("detailDuration");
    this.newPossessionStatus = document.getElementById("newPossessionStatus");

    // Actions
    this.btnToggleNew = document.getElementById("btnToggleNew");
    this.btnSplit = document.getElementById("btnSplit");
    this.btnJoinNext = document.getElementById("btnJoinNext");
    this.btnJoinPrev = document.getElementById("btnJoinPrev");
    this.btnSetStart = document.getElementById("btnSetStart");
    this.btnSetEnd = document.getElementById("btnSetEnd");
    this.btnDelete = document.getElementById("btnDelete");
    this.saveJsonBtn = document.getElementById("saveJsonBtn");

    // Big Video & Fullscreen
    this.theaterModeBtn = document.getElementById("theaterModeBtn");
    this.quickTheaterBtn = document.getElementById("quickTheaterBtn");
    this.fullscreenBtn = document.getElementById("fullscreenBtn");
    this.quickFullscreenBtn = document.getElementById("quickFullscreenBtn");

    // Playback Buttons
    this.playPauseBtn = document.getElementById("playPauseBtn");
    this.stepPrevFrameBtn = document.getElementById("stepPrevFrameBtn");
    this.stepNextFrameBtn = document.getElementById("stepNextFrameBtn");
    this.seekPrevSecBtn = document.getElementById("seekPrevSecBtn");
    this.seekNextSecBtn = document.getElementById("seekNextSecBtn");
    this.seekPrevMinuteBtn = document.getElementById("seekPrevMinuteBtn");
    this.seekNextMinuteBtn = document.getElementById("seekNextMinuteBtn");

    // Dropdowns
    this.openMenuBtn = document.getElementById("openMenuBtn");
    this.openDropdown = document.getElementById("openDropdown");
    this.viewMenuBtn = document.getElementById("viewMenuBtn");
    this.viewDropdown = document.getElementById("viewDropdown");
    this.followToggle = document.getElementById("followCurrentFrameToggle");

    // Canvases
    this.overviewCanvas = document.getElementById("overviewCanvas");
    this.detailCanvas = document.getElementById("detailCanvas");

    // Modal
    this.helpModal = document.getElementById("helpModal");
    this.helpBtn = document.getElementById("helpBtn");
    this.closeHelpModal = document.getElementById("closeHelpModal");
    this.toastContainer = document.getElementById("toastContainer");
  }

  _initTimelines() {
    this.overviewCtx = this.overviewCanvas.getContext("2d");
    this.detailCtx = this.detailCanvas.getContext("2d");
  }

  // ==========================================================================
  // Event Listeners & Wiring
  // ==========================================================================

  _attachEventListeners() {
    // Dropdown Toggles
    this.openMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.openDropdown.parentElement.classList.toggle("open");
      this.viewDropdown.parentElement.classList.remove("open");
    });
    this.viewMenuBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.viewDropdown.parentElement.classList.toggle("open");
      this.openDropdown.parentElement.classList.remove("open");
    });
    document.addEventListener("click", () => {
      this.openDropdown.parentElement.classList.remove("open");
      this.viewDropdown.parentElement.classList.remove("open");
    });

    // File Actions
    document.getElementById("openVideoBtn").addEventListener("click", () => this.videoFileInput.click());
    document.getElementById("openJsonBtn").addEventListener("click", () => this.jsonFileInput.click());
    document.getElementById("loadDemoBtn").addEventListener("click", () => this.loadSampleDemo());

    this.videoFileInput.addEventListener("change", (e) => this._onVideoFileSelected(e));
    this.jsonFileInput.addEventListener("change", (e) => this._onJsonFileSelected(e));
    this.saveJsonBtn.addEventListener("click", () => this.saveJson());

    // Drag and drop video
    this.videoDropArea.addEventListener("dragover", (e) => {
      e.preventDefault();
      this.videoBorder.style.borderColor = "var(--accent-primary)";
    });
    this.videoDropArea.addEventListener("dragleave", () => {
      this._updateVideoBorder();
    });
    this.videoDropArea.addEventListener("drop", (e) => {
      e.preventDefault();
      this._updateVideoBorder();
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        this.loadVideoFile(e.dataTransfer.files[0]);
      }
    });
    this.videoPlaceholder.addEventListener("click", () => this.videoFileInput.click());

    // Big Video / Theater Mode & Fullscreen
    this.theaterModeBtn.addEventListener("click", () => this.toggleTheaterMode());
    this.quickTheaterBtn.addEventListener("click", () => this.toggleTheaterMode());
    this.fullscreenBtn.addEventListener("click", () => this.toggleFullscreen());
    this.quickFullscreenBtn.addEventListener("click", () => this.toggleFullscreen());

    // Panel Toggle Buttons & Floating Tabs
    this.toggleLeftPanelBtn.addEventListener("click", () => this.toggleLeftPanel());
    this.toggleRightPanelBtn.addEventListener("click", () => this.toggleRightPanel());
    this.expandLeftTab.addEventListener("click", () => this.toggleLeftPanel(false));
    this.expandRightTab.addEventListener("click", () => this.toggleRightPanel(false));

    // Playback Controls
    this.playPauseBtn.addEventListener("click", () => this.togglePlayPause());
    this.stepPrevFrameBtn.addEventListener("click", () => this.stepFrame(-1));
    this.stepNextFrameBtn.addEventListener("click", () => this.stepFrame(1));
    this.seekPrevSecBtn.addEventListener("click", () => this.seekSeconds(-1));
    this.seekNextSecBtn.addEventListener("click", () => this.seekSeconds(1));
    this.seekPrevMinuteBtn.addEventListener("click", () => this.seekSeconds(-60));
    this.seekNextMinuteBtn.addEventListener("click", () => this.seekSeconds(60));

    this.speedSelect.addEventListener("change", () => {
      this.video.playbackRate = parseFloat(this.speedSelect.value);
    });

    this.fpsSelect.addEventListener("change", () => {
      if (this.fpsSelect.value !== "auto") {
        this.setFps(parseFloat(this.fpsSelect.value));
      }
    });

    // Edit Actions
    this.btnToggleNew.addEventListener("click", () => this.toggleNewPossession());
    this.btnSplit.addEventListener("click", () => this.splitCurrentPossession());
    this.btnJoinNext.addEventListener("click", () => this.joinNextPossession());
    this.btnJoinPrev.addEventListener("click", () => this.joinPreviousPossession());
    this.btnSetStart.addEventListener("click", () => this.setPossessionStart());
    this.btnSetEnd.addEventListener("click", () => this.setPossessionEnd());
    this.btnDelete.addEventListener("click", () => this.deleteCurrentPossession());

    // View Menu Actions
    document.getElementById("fitOverviewBtn").addEventListener("click", () => this.fitOverviewTimeline());
    document.getElementById("fitDetailBtn").addEventListener("click", () => this.fitDetailTimeline());
    this.followToggle.addEventListener("change", (e) => {
      this.followCurrentFrame = e.target.checked;
    });

    // Modal
    this.helpBtn.addEventListener("click", () => this.helpModal.classList.remove("hidden"));
    this.closeHelpModal.addEventListener("click", () => this.helpModal.classList.add("hidden"));
    this.helpModal.addEventListener("click", (e) => {
      if (e.target === this.helpModal) this.helpModal.classList.add("hidden");
    });

    // HTML5 Video Playback Events
    this.video.addEventListener("timeupdate", () => this._onVideoTimeUpdate());
    this.video.addEventListener("play", () => this.playPauseBtn.textContent = "⏸ Pause");
    this.video.addEventListener("pause", () => this.playPauseBtn.textContent = "▶ Play");
    this.video.addEventListener("ended", () => this.playPauseBtn.textContent = "▶ Play");

    // Timelines Interaction (Click, Drag, Wheel Zoom, Double Click)
    this._setupOverviewTimelineInteractions();
    this._setupDetailTimelineInteractions();

    // Global Keyboard Shortcuts
    window.addEventListener("keydown", (e) => this._onKeyDown(e));

    // Warn before closing with unsaved changes
    window.addEventListener("beforeunload", (e) => {
      if (this.isDirty) {
        e.preventDefault();
        e.returnValue = "You have unsaved possession mapping changes.";
      }
    });
  }

  // ==========================================================================
  // Layout Management: Big Video & Fullscreen
  // ==========================================================================

  toggleTheaterMode() {
    this.isTheaterMode = !this.isTheaterMode;
    if (this.isTheaterMode) {
      this.isLeftCollapsed = true;
      this.isRightCollapsed = true;
      this.appLayout.classList.add("theater-mode");
      this.appLayout.classList.remove("collapse-left", "collapse-right");
      this.expandLeftTab.classList.remove("hidden");
      this.expandRightTab.classList.remove("hidden");
      this.theaterModeBtn.classList.add("active");
      this.quickTheaterBtn.classList.add("active");
      this.showToast("📺 Big Video Mode enabled (Side panels collapsed). Press T to restore.", "info");
    } else {
      this.isLeftCollapsed = false;
      this.isRightCollapsed = false;
      this.appLayout.classList.remove("theater-mode", "collapse-left", "collapse-right");
      this.expandLeftTab.classList.add("hidden");
      this.expandRightTab.classList.add("hidden");
      this.theaterModeBtn.classList.remove("active");
      this.quickTheaterBtn.classList.remove("active");
      this.showToast("Standard View restored.", "info");
    }

    setTimeout(() => {
      this.renderOverviewTimeline();
      this.renderDetailTimeline();
    }, 240);
  }

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      if (this.videoBorder.requestFullscreen) {
        this.videoBorder.requestFullscreen();
      } else if (this.video.requestFullscreen) {
        this.video.requestFullscreen();
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }

  toggleLeftPanel(forceState = null) {
    this.isLeftCollapsed = forceState != null ? forceState : !this.isLeftCollapsed;
    this.appLayout.classList.toggle("collapse-left", this.isLeftCollapsed);
    this.expandLeftTab.classList.toggle("hidden", !this.isLeftCollapsed);

    if (!this.isLeftCollapsed && this.isTheaterMode) {
      this.isTheaterMode = false;
      this.appLayout.classList.remove("theater-mode");
      this.theaterModeBtn.classList.remove("active");
      this.quickTheaterBtn.classList.remove("active");
    }

    setTimeout(() => {
      this.renderOverviewTimeline();
      this.renderDetailTimeline();
    }, 240);
  }

  toggleRightPanel(forceState = null) {
    this.isRightCollapsed = forceState != null ? forceState : !this.isRightCollapsed;
    this.appLayout.classList.toggle("collapse-right", this.isRightCollapsed);
    this.expandRightTab.classList.toggle("hidden", !this.isRightCollapsed);

    if (!this.isRightCollapsed && this.isTheaterMode) {
      this.isTheaterMode = false;
      this.appLayout.classList.remove("theater-mode");
      this.theaterModeBtn.classList.remove("active");
      this.quickTheaterBtn.classList.remove("active");
    }

    setTimeout(() => {
      this.renderOverviewTimeline();
      this.renderDetailTimeline();
    }, 240);
  }

  // ==========================================================================
  // Timeline Canvas Interaction Logic
  // ==========================================================================

  _setupOverviewTimelineInteractions() {
    let isDragging = false;

    const seekAtX = (x) => {
      if (this.totalFrames <= 0) return;
      const rect = this.overviewCanvas.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
      const targetFrame = Math.round(ratio * (this.totalFrames - 1));
      this.seekToFrame(targetFrame);
    };

    this.overviewCanvas.addEventListener("mousedown", (e) => {
      isDragging = true;
      seekAtX(e.clientX);
    });
    window.addEventListener("mousemove", (e) => {
      if (isDragging) seekAtX(e.clientX);
    });
    window.addEventListener("mouseup", () => isDragging = false);

    this.overviewCanvas.addEventListener("dblclick", () => this.fitOverviewTimeline());
  }

  _setupDetailTimelineInteractions() {
    let isDragging = false;

    const frameAtX = (x) => {
      const rect = this.detailCanvas.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
      const range = this.detailVisibleEnd - this.detailVisibleStart;
      return Math.round(this.detailVisibleStart + ratio * range);
    };

    this.detailCanvas.addEventListener("mousedown", (e) => {
      isDragging = true;
      const targetFrame = frameAtX(e.clientX);
      this.seekToFrame(targetFrame);
    });
    window.addEventListener("mousemove", (e) => {
      if (isDragging) {
        const targetFrame = frameAtX(e.clientX);
        this.seekToFrame(targetFrame);
      }
    });
    window.addEventListener("mouseup", () => isDragging = false);

    // Mouse wheel zoom centered on pointer
    this.detailCanvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (this.totalFrames <= 0) return;

      const rect = this.detailCanvas.getBoundingClientRect();
      const pointerRatio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const currentRange = this.detailVisibleEnd - this.detailVisibleStart;
      const pointerFrame = this.detailVisibleStart + pointerRatio * currentRange;

      const zoomFactor = e.deltaY < 0 ? 0.75 : 1.35; // scroll up = zoom in
      const newRange = Math.max(15, Math.min(this.totalFrames, Math.round(currentRange * zoomFactor)));

      let newStart = Math.round(pointerFrame - pointerRatio * newRange);
      let newEnd = newStart + newRange;

      if (newStart < 0) {
        newStart = 0;
        newEnd = Math.min(this.totalFrames - 1, newRange);
      }
      if (newEnd >= this.totalFrames) {
        newEnd = this.totalFrames - 1;
        newStart = Math.max(0, newEnd - newRange);
      }

      this.detailVisibleStart = newStart;
      this.detailVisibleEnd = newEnd;
      this.renderDetailTimeline();
    }, { passive: false });

    this.detailCanvas.addEventListener("dblclick", () => this.fitDetailTimeline());
  }

  // ==========================================================================
  // Keyboard Shortcuts (Matching design/ui-rules.md)
  // ==========================================================================

  _onKeyDown(e) {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) {
      return;
    }

    // Ctrl+S / Cmd+S: Save JSON
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      this.saveJson();
      return;
    }

    // Ctrl+0: Fit Overview
    if ((e.ctrlKey || e.metaKey) && e.key === "0") {
      e.preventDefault();
      this.fitOverviewTimeline();
      return;
    }

    // Ctrl+1: Fit Detail
    if ((e.ctrlKey || e.metaKey) && e.key === "1") {
      e.preventDefault();
      this.fitDetailTimeline();
      return;
    }

    // Playback Shortcuts
    if (e.code === "Space") {
      e.preventDefault();
      this.togglePlayPause();
      return;
    }

    if (e.key === "ArrowLeft") {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) this.seekSeconds(-60);
      else if (e.shiftKey) this.seekSeconds(-1);
      else this.stepFrame(-1);
      return;
    }

    if (e.key === "ArrowRight") {
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) this.seekSeconds(60);
      else if (e.shiftKey) this.seekSeconds(1);
      else this.stepFrame(1);
      return;
    }

    // Up / Down: Previous / Next Possession
    if (e.key === "ArrowUp") {
      e.preventDefault();
      this.selectRelativePossession(-1);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      this.selectRelativePossession(1);
      return;
    }

    // Home / End: Seek to possession start / end
    if (e.key === "Home") {
      e.preventDefault();
      this.seekToPossessionBoundary("start");
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      this.seekToPossessionBoundary("end");
      return;
    }

    // Escape: Cancel creation or clear selection
    if (e.key === "Escape") {
      e.preventDefault();
      this.cancelOrClear();
      return;
    }

    // N: Start / End new possession
    if (e.key.toLowerCase() === "n") {
      e.preventDefault();
      this.toggleNewPossession();
      return;
    }

    // S: Split
    if (e.key.toLowerCase() === "s") {
      e.preventDefault();
      this.splitCurrentPossession();
      return;
    }

    // J: Join Next, Shift+J: Join Previous
    if (e.key.toLowerCase() === "j") {
      e.preventDefault();
      if (e.shiftKey) this.joinPreviousPossession();
      else this.joinNextPossession();
      return;
    }

    // [: Move active possession start here
    if (e.key === "[") {
      e.preventDefault();
      this.setPossessionStart();
      return;
    }

    // ]: Move active possession end here
    if (e.key === "]") {
      e.preventDefault();
      this.setPossessionEnd();
      return;
    }

    // Delete / Backspace: Delete active possession
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      this.deleteCurrentPossession();
      return;
    }

    // T: Toggle Big Video / Theater Mode
    if (e.key.toLowerCase() === "t") {
      e.preventDefault();
      this.toggleTheaterMode();
      return;
    }

    // F: Toggle Fullscreen
    if (e.key.toLowerCase() === "f") {
      e.preventDefault();
      this.toggleFullscreen();
      return;
    }

    // P: Toggle Left Panel (Possessions)
    if (e.key.toLowerCase() === "p") {
      e.preventDefault();
      this.toggleLeftPanel();
      return;
    }

    // A: Toggle Right Panel (Actions)
    if (e.key.toLowerCase() === "a") {
      e.preventDefault();
      this.toggleRightPanel();
      return;
    }
  }

  // ==========================================================================
  // Video & Frame Operations
  // ==========================================================================

  timestampForFrame(frame) {
    return frame / this.fps;
  }

  frameForTimestamp(seconds) {
    return Math.round(seconds * this.fps);
  }

  setFps(fps) {
    if (fps <= 0) return;
    this.fps = fps;
    this.currentFpsLabel.textContent = `(${this.fps.toFixed(2)} fps)`;
    this.fpsSelect.value = String(fps);
    if (this.videoDuration > 0) {
      this.totalFrames = Math.max(1, Math.round(this.videoDuration * this.fps));
    }
    this._updateUI();
  }

  loadVideoFile(file) {
    this.isDemoActive = false;
    this.demoCanvas.classList.add("hidden");
    this.video.classList.remove("hidden");
    this.videoPlaceholder.classList.add("hidden");

    this.loadedFileName = file.name.replace(/\.[^/.]+$/, "");
    const url = URL.createObjectURL(file);
    this.video.src = url;
    this.video.load();

    this.video.onloadedmetadata = () => {
      this.videoDuration = this.video.duration;
      this.totalFrames = Math.max(1, Math.round(this.videoDuration * this.fps));
      this.detailVisibleStart = 0;
      this.detailVisibleEnd = Math.min(this.totalFrames - 1, 300);
      this.showToast(`Loaded video: ${file.name} (${formatTimestamp(this.videoDuration)})`, "success");
      this.statusMessage.textContent = `Video: ${file.name} | Total frames: ${this.totalFrames}`;
      this._updateUI();
      this.fitOverviewTimeline();
    };
  }

  _onVideoFileSelected(e) {
    if (e.target.files && e.target.files[0]) {
      this.loadVideoFile(e.target.files[0]);
    }
  }

  _onJsonFileSelected(e) {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        this.loadPossessionsJson(json);
        this.showToast(`Successfully loaded mapping: ${file.name}`, "success");
      } catch (err) {
        this.showToast(`Error parsing JSON: ${err.message}`, "error");
      }
    };
    reader.readAsText(file);
  }

  loadPossessionsJson(rawList) {
    if (!Array.isArray(rawList)) {
      throw new Error("Mapping JSON root must be an array of possessions.");
    }

    const decoded = rawList.map((raw, idx) => {
      const extra = {};
      const standardKeys = ["possession-num", "start-frame", "start-time", "end-frame", "end-time"];
      for (const [k, v] of Object.entries(raw)) {
        if (!standardKeys.includes(k)) extra[k] = v;
      }
      return new Possession(
        raw["possession-num"] ?? (idx + 1),
        raw["start-frame"],
        raw["start-time"],
        raw["end-frame"],
        raw["end-time"],
        extra
      );
    });

    // Auto-detect FPS from first valid possession duration
    for (const p of decoded) {
      if (p.duration_frames > 1 && p.duration_time > 0) {
        const estimatedFps = (p.duration_frames - 1) / p.duration_time;
        if (estimatedFps > 10 && estimatedFps < 120) {
          const standardFpsList = [24, 25, 29.97, 30, 50, 59.94, 60];
          const closest = standardFpsList.reduce((prev, curr) =>
            Math.abs(curr - estimatedFps) < Math.abs(prev - estimatedFps) ? curr : prev
          );
          if (Math.abs(closest - estimatedFps) < 0.5) {
            this.setFps(closest);
          }
          break;
        }
      }
    }

    this.possessions = decoded.sort((a, b) => a.start_frame - b.start_frame);
    if (this.possessions.length > 0) {
      const lastPossessionEnd = this.possessions[this.possessions.length - 1].end_frame;
      if (lastPossessionEnd >= this.totalFrames) {
        this.totalFrames = lastPossessionEnd + 60;
      }
      this.selectedIndex = 0;
    }

    this.isDirty = false;
    this._updateUI();
    this.fitDetailTimeline();
  }

  togglePlayPause() {
    if (this.isDemoActive) {
      this.demoPlaying = !this.demoPlaying;
      this.playPauseBtn.textContent = this.demoPlaying ? "⏸ Pause" : "▶ Play";
      return;
    }
    if (!this.video.src) return;
    if (this.video.paused) {
      this.video.play();
    } else {
      this.video.pause();
    }
  }

  seekToFrame(frame) {
    const clamped = Math.max(0, Math.min(frame, Math.max(0, this.totalFrames - 1)));
    this.currentFrame = clamped;

    if (this.isDemoActive) {
      this._updateUI();
      return;
    }

    if (this.video && this.video.duration) {
      this.video.currentTime = clamped / this.fps;
    }
    this._updateUI();
  }

  stepFrame(delta) {
    if (this.video && !this.video.paused) this.video.pause();
    this.seekToFrame(this.currentFrame + delta);
  }

  seekSeconds(delta) {
    if (this.video && !this.video.paused) this.video.pause();
    this.seekToFrame(this.currentFrame + Math.round(delta * this.fps));
  }

  _onVideoTimeUpdate() {
    if (this.isDemoActive) return;
    const frame = Math.round(this.video.currentTime * this.fps);
    if (frame !== this.currentFrame) {
      this.currentFrame = frame;
      if (this.followCurrentFrame) {
        this._followFrameIntoDetailView();
      }
      this._updateUI();
    }
  }

  _followFrameIntoDetailView() {
    const range = this.detailVisibleEnd - this.detailVisibleStart;
    if (this.currentFrame < this.detailVisibleStart || this.currentFrame > this.detailVisibleEnd) {
      this.detailVisibleStart = Math.max(0, this.currentFrame - Math.round(range * 0.3));
      this.detailVisibleEnd = Math.min(this.totalFrames - 1, this.detailVisibleStart + range);
    }
  }

  // ==========================================================================
  // Editing Actions (Start/End New, Split, Join, Stretch, Delete)
  // ==========================================================================

  toggleNewPossession() {
    if (this.newPossessionStartFrame == null) {
      // Start creating new possession at current frame
      this.newPossessionStartFrame = this.currentFrame;
      this.showToast(`New possession started at frame ${this.currentFrame}. Move to end frame and press N.`, "success");
    } else {
      // Complete new possession from start to current frame
      const start = Math.min(this.newPossessionStartFrame, this.currentFrame);
      const end = Math.max(this.newPossessionStartFrame, this.currentFrame);
      try {
        const result = this.editor.create(this.possessions, start, end, (f) => this.timestampForFrame(f));
        this.possessions = result.possessions;
        this.selectedIndex = result.selectedIndex;
        this.newPossessionStartFrame = null;
        this.markDirty();
        this.showToast(`Created possession covering frames ${start}–${end}`, "success");
      } catch (err) {
        this.showToast(err.message, "error");
      }
    }
    this._updateUI();
  }

  splitCurrentPossession() {
    const active = this.getActivePossession();
    if (!active) {
      this.showToast("Current frame is not inside an active possession.", "error");
      return;
    }
    try {
      const activeIdx = this.possessions.indexOf(active);
      const result = this.editor.split(this.possessions, activeIdx, this.currentFrame, (f) => this.timestampForFrame(f));
      this.possessions = result.possessions;
      this.selectedIndex = result.selectedIndex;
      this.markDirty();
      this.showToast(`Split possession at frame ${this.currentFrame}`, "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  joinNextPossession() {
    const idx = this.selectedIndex ?? this.getActivePossessionIndex();
    if (idx == null) {
      this.showToast("No possession selected to join.", "error");
      return;
    }
    try {
      const result = this.editor.joinNext(this.possessions, idx, (f) => this.timestampForFrame(f));
      this.possessions = result.possessions;
      this.selectedIndex = result.selectedIndex;
      this.markDirty();
      this.showToast("Joined with following possession.", "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  joinPreviousPossession() {
    const idx = this.selectedIndex ?? this.getActivePossessionIndex();
    if (idx == null) {
      this.showToast("No possession selected to join.", "error");
      return;
    }
    try {
      const result = this.editor.joinPrevious(this.possessions, idx, (f) => this.timestampForFrame(f));
      this.possessions = result.possessions;
      this.selectedIndex = result.selectedIndex;
      this.markDirty();
      this.showToast("Joined with previous possession.", "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  setPossessionStart() {
    const idx = this.selectedIndex ?? this.getActivePossessionIndex();
    if (idx == null) {
      this.showToast("No possession selected.", "error");
      return;
    }
    try {
      const result = this.editor.setStart(this.possessions, idx, this.currentFrame, (f) => this.timestampForFrame(f));
      this.possessions = result.possessions;
      this.selectedIndex = result.selectedIndex;
      this.markDirty();
      this.showToast(`Moved start to frame ${this.currentFrame}`, "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  setPossessionEnd() {
    const idx = this.selectedIndex ?? this.getActivePossessionIndex();
    if (idx == null) {
      this.showToast("No possession selected.", "error");
      return;
    }
    try {
      const result = this.editor.setEnd(this.possessions, idx, this.currentFrame, (f) => this.timestampForFrame(f));
      this.possessions = result.possessions;
      this.selectedIndex = result.selectedIndex;
      this.markDirty();
      this.showToast(`Moved end to frame ${this.currentFrame}`, "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  deleteCurrentPossession() {
    const idx = this.selectedIndex ?? this.getActivePossessionIndex();
    if (idx == null) {
      this.showToast("No possession selected to delete.", "error");
      return;
    }
    const item = this.possessions[idx];
    if (!confirm(`Are you sure you want to delete possession #${item.possession_num}?`)) {
      return;
    }
    try {
      const result = this.editor.delete(this.possessions, idx);
      this.possessions = result.possessions;
      this.selectedIndex = null;
      this.markDirty();
      this.showToast(`Deleted possession #${item.possession_num}`, "success");
    } catch (err) {
      this.showToast(err.message, "error");
    }
    this._updateUI();
  }

  cancelOrClear() {
    if (this.newPossessionStartFrame != null) {
      this.newPossessionStartFrame = null;
      this.showToast("Cancelled new possession creation.", "success");
    } else if (this.selectedIndex != null) {
      this.selectedIndex = null;
    }
    this._updateUI();
  }

  selectRelativePossession(direction) {
    if (this.possessions.length === 0) return;
    let nextIdx = (this.selectedIndex ?? 0) + direction;
    if (nextIdx < 0) nextIdx = 0;
    if (nextIdx >= this.possessions.length) nextIdx = this.possessions.length - 1;
    this.selectPossession(nextIdx, true);
  }

  selectPossession(index, seekToStart = false) {
    if (index >= 0 && index < this.possessions.length) {
      this.selectedIndex = index;
      if (seekToStart) {
        this.seekToFrame(this.possessions[index].start_frame);
      }
      this.fitDetailTimeline();
      this._updateUI();
    }
  }

  seekToPossessionBoundary(which = "start") {
    const current = this.getSelectedOrActivePossession();
    if (!current) return;
    const target = which === "start" ? current.start_frame : current.end_frame;
    this.seekToFrame(target);
  }

  getActivePossessionIndex() {
    return this.possessions.findIndex(
      (p) => p.start_frame <= this.currentFrame && this.currentFrame <= p.end_frame
    );
  }

  getActivePossession() {
    const idx = this.getActivePossessionIndex();
    return idx !== -1 ? this.possessions[idx] : null;
  }

  getSelectedOrActivePossession() {
    if (this.selectedIndex != null && this.possessions[this.selectedIndex]) {
      return this.possessions[this.selectedIndex];
    }
    return this.getActivePossession();
  }

  markDirty() {
    this.isDirty = true;
    this.dirtyIndicator.classList.remove("hidden");
    this.saveJsonBtn.disabled = false;
  }

  saveJson() {
    if (this.possessions.length === 0) {
      this.showToast("No possessions to save.", "error");
      return;
    }
    const data = this.possessions.map((p) => p.toJSON());
    const jsonStr = JSON.stringify(data, null, 2) + "\n";
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${this.loadedFileName}.possession.json`;
    a.click();
    URL.revokeObjectURL(url);

    this.isDirty = false;
    this.dirtyIndicator.classList.add("hidden");
    this.showToast(`Saved ${this.loadedFileName}.possession.json`, "success");
  }

  // ==========================================================================
  // Timeline Zoom & Fit Operations
  // ==========================================================================

  fitOverviewTimeline() {
    this.renderOverviewTimeline();
  }

  fitDetailTimeline() {
    const current = this.getSelectedOrActivePossession();
    if (current) {
      const buffer = Math.max(15, Math.round(current.duration_frames * 0.4));
      this.detailVisibleStart = Math.max(0, current.start_frame - buffer);
      this.detailVisibleEnd = Math.min(this.totalFrames - 1, current.end_frame + buffer);
    } else if (this.totalFrames > 0) {
      const range = 180; // 6 seconds at 30 fps
      this.detailVisibleStart = Math.max(0, this.currentFrame - Math.round(range / 2));
      this.detailVisibleEnd = Math.min(this.totalFrames - 1, this.detailVisibleStart + range);
    }
    this.renderDetailTimeline();
  }

  // ==========================================================================
  // UI Rendering & Updates
  // ==========================================================================

  _updateUI() {
    const active = this.getActivePossession();
    const activeIndex = this.getActivePossessionIndex();
    const isCreating = this.newPossessionStartFrame != null;
    const selected = this.getSelectedOrActivePossession();

    // 1. Current Time & Frame Readout
    const currentTimeSec = this.currentFrame / this.fps;
    this.currentReadout.querySelector(".readout-frame").textContent = `Current frame ${this.currentFrame}`;
    this.currentReadout.querySelector(".readout-time").textContent = formatTimestamp(currentTimeSec);
    this.overviewMeta.textContent = `${this.totalFrames} frames · ${formatTimestamp(this.totalFrames / this.fps)}`;

    // 2. Video Border State
    this.videoBorder.classList.remove("state-active", "state-creating");
    if (isCreating) {
      this.videoBorder.classList.add("state-creating");
    } else if (active) {
      this.videoBorder.classList.add("state-active");
    }

    // 3. Active Possession Badge
    this.activeBadge.classList.remove("badge-neutral", "badge-active", "badge-creating");
    if (isCreating) {
      this.activeBadge.classList.add("badge-creating");
      this.activeBadge.textContent = `CREATING NEW (FROM FRAME ${this.newPossessionStartFrame})`;
    } else if (active) {
      this.activeBadge.classList.add("badge-active");
      this.activeBadge.textContent = `ACTIVE POSSESSION: #${active.possession_num}`;
    } else {
      this.activeBadge.classList.add("badge-neutral");
      this.activeBadge.textContent = "NO ACTIVE POSSESSION";
    }

    // 4. Details Card
    if (selected) {
      this.detailNum.textContent = `#${selected.possession_num}`;
      this.detailStartFrame.textContent = `${selected.start_frame}`;
      this.detailStartTime.textContent = `${formatTimestamp(selected.start_time)}`;
      this.detailEndFrame.textContent = `${selected.end_frame}`;
      this.detailEndTime.textContent = `${formatTimestamp(selected.end_time)}`;
      this.detailDuration.textContent = `${selected.duration_frames}f (${formatTimestamp(selected.duration_time)})`;
    } else {
      this.detailNum.textContent = "—";
      this.detailStartFrame.textContent = "—";
      this.detailStartTime.textContent = "—";
      this.detailEndFrame.textContent = "—";
      this.detailEndTime.textContent = "—";
      this.detailDuration.textContent = "—";
    }

    if (isCreating) {
      this.newPossessionStatus.textContent = `New possession start: frame ${this.newPossessionStartFrame}`;
    } else {
      this.newPossessionStatus.textContent = "New possession start: not set";
    }

    // 5. Action Buttons Enable/Disable State
    this.btnToggleNew.textContent = isCreating ? "End new possession [N]" : "Start a new possession [N]";
    this.btnToggleNew.classList.toggle("creating-mode", isCreating);

    const canEdit = selected != null;
    this.btnSplit.disabled = !active; // split is only valid when inside active possession
    this.btnJoinNext.disabled = !canEdit || (this.selectedIndex ?? activeIndex) >= this.possessions.length - 1;
    this.btnJoinPrev.disabled = !canEdit || (this.selectedIndex ?? activeIndex) <= 0;
    this.btnSetStart.disabled = !canEdit;
    this.btnSetEnd.disabled = !canEdit;
    this.btnDelete.disabled = !canEdit;

    // 6. Possession Table List
    this._renderPossessionTable(activeIndex);

    // 7. Render Timelines
    this.renderOverviewTimeline();
    this.renderDetailTimeline();
  }

  _updateVideoBorder() {
    this.videoBorder.style.borderColor = "";
    if (this.newPossessionStartFrame != null) {
      this.videoBorder.classList.add("state-creating");
    } else if (this.getActivePossession()) {
      this.videoBorder.classList.add("state-active");
    }
  }

  _renderPossessionTable(activeIndex) {
    this.possessionCount.textContent = String(this.possessions.length);

    if (this.possessions.length === 0) {
      this.possessionListBody.innerHTML = `
        <tr class="empty-row">
          <td colspan="4">No possessions loaded</td>
        </tr>`;
      return;
    }

    const rowsHtml = this.possessions.map((p, idx) => {
      const isSelected = idx === this.selectedIndex;
      const isActiveFrame = idx === activeIndex;
      const classes = [
        isSelected ? "selected" : "",
        isActiveFrame ? "active-frame-possession" : ""
      ].filter(Boolean).join(" ");

      return `
        <tr class="${classes}" data-index="${idx}">
          <td class="col-num">${p.possession_num}</td>
          <td>${p.start_frame}</td>
          <td>${p.end_frame}</td>
          <td>${p.duration_frames}f</td>
        </tr>`;
    }).join("");

    this.possessionListBody.innerHTML = rowsHtml;

    // Table click handler
    this.possessionListBody.querySelectorAll("tr[data-index]").forEach((tr) => {
      tr.addEventListener("click", () => {
        const idx = parseInt(tr.dataset.index, 10);
        this.selectPossession(idx, true);
      });
    });
  }

  // ==========================================================================
  // Timeline Canvas Painters
  // ==========================================================================

  renderOverviewTimeline() {
    const canvas = this.overviewCanvas;
    const ctx = this.overviewCtx;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    const w = rect.width;
    const h = 32;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Clear & background
    ctx.fillStyle = "#0b1120";
    ctx.fillRect(0, 0, w, h);

    if (this.totalFrames <= 0) return;

    // Track baseline
    const trackY = 7;
    const trackH = 18;
    ctx.fillStyle = "#1e293b";
    ctx.fillRect(0, trackY, w, trackH);

    const xForFrame = (f) => (f / (this.totalFrames - 1)) * w;

    // Draw detail visible viewport window
    if (this.detailVisibleEnd > this.detailVisibleStart) {
      const vx1 = xForFrame(this.detailVisibleStart);
      const vx2 = xForFrame(this.detailVisibleEnd);
      ctx.fillStyle = "rgba(148, 163, 184, 0.15)";
      ctx.fillRect(vx1, 0, Math.max(2, vx2 - vx1), h);
      ctx.strokeStyle = "rgba(148, 163, 184, 0.35)";
      ctx.lineWidth = 1;
      ctx.strokeRect(vx1, 0, Math.max(2, vx2 - vx1), h);
    }

    // Draw possessions
    for (let i = 0; i < this.possessions.length; i++) {
      const p = this.possessions[i];
      const x1 = xForFrame(p.start_frame);
      const x2 = xForFrame(p.end_frame);
      const blockW = Math.max(2, x2 - x1);

      ctx.fillStyle = (i === this.selectedIndex) ? "#60a5fa" : "#2563eb";
      ctx.fillRect(x1, trackY + 1, blockW, trackH - 2);

      // Possession label if wide enough
      if (blockW > 16) {
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 8.5px var(--font-family)";
        ctx.fillText(`P${p.possession_num}`, x1 + 2, trackY + 12);
      }
    }

    // Draw tentative new possession preview bar
    if (this.newPossessionStartFrame != null) {
      const start = Math.min(this.newPossessionStartFrame, this.currentFrame);
      const end = Math.max(this.newPossessionStartFrame, this.currentFrame);
      const px1 = xForFrame(start);
      const px2 = xForFrame(end);
      ctx.fillStyle = "rgba(34, 197, 94, 0.75)";
      ctx.fillRect(px1, trackY, Math.max(2, px2 - px1), trackH);
    }

    // Current frame needle
    const needleX = xForFrame(this.currentFrame);
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(needleX, 0);
    ctx.lineTo(needleX, h);
    ctx.stroke();

    // Triangle cap
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(needleX - 4, 0);
    ctx.lineTo(needleX + 4, 0);
    ctx.lineTo(needleX, 5);
    ctx.closePath();
    ctx.fill();
  }

  renderDetailTimeline() {
    const canvas = this.detailCanvas;
    const ctx = this.detailCtx;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;

    const w = rect.width;
    const h = 64;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Background
    ctx.fillStyle = "#080d1a";
    ctx.fillRect(0, 0, w, h);

    if (this.totalFrames <= 0) return;

    if (this.detailVisibleEnd <= this.detailVisibleStart) {
      this.detailVisibleStart = Math.max(0, this.currentFrame - 60);
      this.detailVisibleEnd = Math.min(this.totalFrames - 1, this.currentFrame + 60);
    }

    const range = Math.max(1, this.detailVisibleEnd - this.detailVisibleStart);
    const xForFrame = (f) => ((f - this.detailVisibleStart) / range) * w;

    // Draw Ruler & Tick Marks (Compact)
    const tickInterval = range > 300 ? 30 : (range > 100 ? 10 : (range > 40 ? 5 : 1));
    const startTick = Math.floor(this.detailVisibleStart / tickInterval) * tickInterval;

    ctx.font = "9px var(--font-mono)";
    for (let f = startTick; f <= this.detailVisibleEnd; f += tickInterval) {
      const tx = xForFrame(f);
      if (tx < 0 || tx > w) continue;

      const isMajor = (f % (tickInterval * 2) === 0);
      const tickH = isMajor ? 8 : 4;

      ctx.strokeStyle = isMajor ? "#475569" : "#334155";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(tx, 0);
      ctx.lineTo(tx, tickH);
      ctx.stroke();

      if (isMajor && range < 500) {
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(String(f), tx + 2, 12);
      }
    }

    // Possession Track Area
    const trackY = 16;
    const trackH = 38;

    // Possessions
    for (let i = 0; i < this.possessions.length; i++) {
      const p = this.possessions[i];
      if (p.end_frame < this.detailVisibleStart || p.start_frame > this.detailVisibleEnd) {
        continue;
      }

      const x1 = xForFrame(p.start_frame);
      const x2 = xForFrame(p.end_frame);
      const blockW = Math.max(3, x2 - x1);
      const isSelected = (i === this.selectedIndex);

      // Block Fill
      ctx.fillStyle = isSelected ? "#3b82f6" : "rgba(37, 99, 235, 0.75)";
      ctx.fillRect(x1, trackY, blockW, trackH);

      // Block Border
      ctx.strokeStyle = isSelected ? "#93c5fd" : "#1d4ed8";
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.strokeRect(x1, trackY, blockW, trackH);

      // Start & End boundary brackets
      ctx.fillStyle = "#93c5fd";
      ctx.fillRect(x1, trackY, 2.5, trackH);
      ctx.fillRect(x2 - 2.5, trackY, 2.5, trackH);

      // Text label inside block
      if (blockW > 35) {
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 10px var(--font-family)";
        ctx.fillText(`P#${p.possession_num}`, x1 + 5, trackY + 15);
        ctx.font = "9px var(--font-mono)";
        ctx.fillStyle = "#dbeafe";
        ctx.fillText(`${p.duration_frames}f (${formatTimestamp(p.duration_time)})`, x1 + 5, trackY + 28);
      }
    }

    // Tentative New Possession Bar
    if (this.newPossessionStartFrame != null) {
      const start = Math.min(this.newPossessionStartFrame, this.currentFrame);
      const end = Math.max(this.newPossessionStartFrame, this.currentFrame);
      const nx1 = xForFrame(start);
      const nx2 = xForFrame(end);
      const nw = Math.max(3, nx2 - nx1);

      ctx.fillStyle = "rgba(34, 197, 94, 0.65)";
      ctx.fillRect(nx1, trackY, nw, trackH);
      ctx.strokeStyle = "#86efac";
      ctx.lineWidth = 2;
      ctx.strokeRect(nx1, trackY, nw, trackH);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 10px var(--font-family)";
      ctx.fillText(`New (${end - start + 1}f)`, nx1 + 5, trackY + 20);
    }

    // Current frame vertical needle
    const needleX = xForFrame(this.currentFrame);
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(needleX, 0);
    ctx.lineTo(needleX, h);
    ctx.stroke();

    // Triangle cap
    ctx.fillStyle = "#facc15";
    ctx.beginPath();
    ctx.moveTo(needleX - 5, 0);
    ctx.lineTo(needleX + 5, 0);
    ctx.lineTo(needleX, 7);
    ctx.closePath();
    ctx.fill();

    // Frame tag at needle base
    ctx.fillStyle = "#facc15";
    ctx.font = "bold 9px var(--font-mono)";
    ctx.fillText(`f${this.currentFrame}`, needleX + 3, h - 3);
  }

  // ==========================================================================
  // Sample Demo Generator (Runs Immediately Without Any User Files!)
  // ==========================================================================

  loadSampleDemo() {
    this.isDemoActive = true;
    this.loadedFileName = "basketball-sample-demo";
    this.video.classList.add("hidden");
    this.videoPlaceholder.classList.add("hidden");
    this.demoCanvas.classList.remove("hidden");

    this.fps = 30.0;
    this.totalFrames = 1200; // 40 seconds demo match
    this.videoDuration = 40.0;
    this.currentFrame = 45;
    this.demoPlaying = false;

    // Fetch or use demo possessions
    fetch("demo-possessions.json")
      .then((res) => res.json())
      .then((json) => {
        this.loadPossessionsJson(json);
        this.showToast("Loaded Sample Basketball Demo (Video + 4 Possessions)", "success");
      })
      .catch(() => {
        // Fallback default demo data
        const fallback = [
          { "possession-num": 1, "start-frame": 30, "start-time": 1.0, "end-frame": 180, "end-time": 6.0 },
          { "possession-num": 2, "start-frame": 240, "start-time": 8.0, "end-frame": 450, "end-time": 15.0 },
          { "possession-num": 3, "start-frame": 510, "start-time": 17.0, "end-frame": 750, "end-time": 25.0 },
          { "possession-num": 4, "start-frame": 820, "start-time": 27.33, "end-frame": 1100, "end-time": 36.67 }
        ];
        this.loadPossessionsJson(fallback);
        this.showToast("Loaded Sample Basketball Demo (Fallback)", "success");
      });

    this._startDemoLoop();
    this.fitDetailTimeline();
    this._updateUI();
  }

  _startDemoLoop() {
    if (this._demoLoopActive) return;
    this._demoLoopActive = true;

    let lastTime = performance.now();
    const courtCanvas = this.demoCanvas;
    const ctx = courtCanvas.getContext("2d");

    const renderCourt = (now) => {
      if (this.isDemoActive) {
        const deltaSec = (now - lastTime) / 1000;
        lastTime = now;

        if (this.demoPlaying) {
          this.currentFrame += Math.round(deltaSec * this.fps);
          if (this.currentFrame >= this.totalFrames) {
            this.currentFrame = 0;
          }
          if (this.followCurrentFrame) {
            this._followFrameIntoDetailView();
          }
          this._updateUI();
        }

        // Draw animated basketball match court
        const dpr = window.devicePixelRatio || 1;
        const rect = courtCanvas.getBoundingClientRect();
        courtCanvas.width = rect.width * dpr;
        courtCanvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;

        // Hardwood Court
        const grad = ctx.createLinearGradient(0, 0, w, h);
        grad.addColorStop(0, "#c27c38");
        grad.addColorStop(1, "#a05a1d");
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, w, h);

        // Court lines (white)
        ctx.strokeStyle = "rgba(255, 255, 255, 0.85)";
        ctx.lineWidth = 3;
        ctx.strokeRect(20, 20, w - 40, h - 40);

        // Center line & circle
        ctx.beginPath();
        ctx.moveTo(w / 2, 20);
        ctx.lineTo(w / 2, h - 20);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(w / 2, h / 2, 50, 0, Math.PI * 2);
        ctx.stroke();

        // 3-point arcs & paint keys
        ctx.strokeRect(20, (h - 100) / 2, 100, 100);
        ctx.strokeRect(w - 120, (h - 100) / 2, 100, 100);

        // Basketball Hoops
        ctx.strokeStyle = "#e11d48";
        ctx.lineWidth = 4;
        ctx.strokeRect(24, (h - 30) / 2, 6, 30);
        ctx.strokeRect(w - 30, (h - 30) / 2, 6, 30);

        // Animated Players
        const t = this.currentFrame / 30;
        const drawPlayer = (x, y, teamColor, num) => {
          ctx.fillStyle = teamColor;
          ctx.beginPath();
          ctx.arc(x, y, 12, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 2;
          ctx.stroke();

          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 9px var(--font-family)";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(String(num), x, y);
        };

        // Team Blue Players
        drawPlayer(w * 0.35 + Math.sin(t * 1.5) * 40, h * 0.4 + Math.cos(t) * 20, "#1d4ed8", 7);
        drawPlayer(w * 0.42 + Math.cos(t * 1.2) * 35, h * 0.65 + Math.sin(t * 0.8) * 30, "#1d4ed8", 23);
        drawPlayer(w * 0.25 + Math.sin(t * 0.9) * 25, h * 0.5 + Math.cos(t * 1.1) * 20, "#1d4ed8", 11);

        // Team Red Players
        drawPlayer(w * 0.55 + Math.cos(t * 1.4) * 40, h * 0.45 + Math.sin(t * 1.3) * 25, "#b91c1c", 30);
        drawPlayer(w * 0.62 + Math.sin(t * 1.1) * 30, h * 0.6 + Math.cos(t * 0.9) * 25, "#b91c1c", 34);

        // Basketball (orange)
        const bx = w * 0.4 + Math.sin(t * 2.5) * 60;
        const by = h * 0.5 + Math.cos(t * 2.5) * 40;
        ctx.fillStyle = "#f97316";
        ctx.beginPath();
        ctx.arc(bx, by, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = 1;
        ctx.stroke();

        // On-screen HUD / Timecode Overlay
        ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
        ctx.fillRect(16, 16, 220, 48);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 13px var(--font-mono)";
        ctx.textAlign = "left";
        ctx.textBaseline = "top";
        ctx.fillText(`FRAME: ${this.currentFrame}`, 24, 22);
        ctx.font = "11px var(--font-mono)";
        ctx.fillStyle = "#38bdf8";
        ctx.fillText(`TIME:  ${formatTimestamp(this.currentFrame / this.fps)}`, 24, 42);
      }

      requestAnimationFrame(renderCourt);
    };

    requestAnimationFrame(renderCourt);
  }

  // ==========================================================================
  // Toast Notifications
  // ==========================================================================

  showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }
}

// ============================================================================
// Initialization on DOM Ready
// ============================================================================

window.addEventListener("DOMContentLoaded", () => {
  window.app = new App();
});
