# Implementation Status

Last updated: 2026-08-08

## Current iteration: 6. Current-possession status

### Completed

- Added `main.py` as the application entrypoint.
- Added the initial PySide6 three-column application shell.
- Added a replaceable `VideoPlayer` interface and native libmpv `wid` backend.
- Added video loading, play/pause, relative seeking, frame stepping, time display, and safe player shutdown.
- Added dependency declarations, setup instructions, and dependency-free timestamp tests.
- Passed thirty-one standard-library unit tests, Python compilation, and whitespace validation.
- Reset `LC_NUMERIC` to `C` before libmpv initialization, as required after Qt locale setup.
- Registered the time observer through a stored plain function because python-mpv annotates callbacks and cannot annotate bound methods.
- Confirmed that the application launches and native libmpv initializes in the user-managed environment.
- Added a schema-neutral mapping document and replaceable JSON codec.
- Added atomic JSON writes with five adjacent rotating backups.
- Added Open JSON, Save, dirty-state display, and unsaved-close confirmation to the UI shell.
- Added dependency-free mapping persistence tests.
- Added a typed possession model and codec for the temporary list-based JSON schema.
- Preserved unknown possession fields during JSON round trips.
- Populated the possession list with possession number and inclusive frame boundaries.
- Added a compact integer-PTS `FrameIndex` with VFR-safe frame/time lookup.
- Added a replaceable ffprobe index provider and fingerprint-validated sidecar cache.
- Moved frame-index construction off the Qt UI thread with cancellable ffprobe execution.
- Added exact current-frame display and absolute frame seeking from possession selection.
- Disabled audio, interpolation, deinterlacing, and frame dropping in the libmpv backend.
- Added dependency-free frame-index and cache tests.
- Made frame-index loading/building application-modal with an indeterminate progress bar and cancellation.
- Streamed ffprobe frame timestamps to show processed time against total video duration while reducing indexing memory use.
- Added a UI-independent possession editor for inclusive create, delete, split, join, and boundary edits.
- Added overlap rejection, frame-derived timestamps, frame-order sorting, and possession renumbering.
- Connected current-possession actions, two-stage creation, delete confirmation, dirty-state tracking, and action availability.
- Added playback, possession-selection, editing, boundary-selection, and boundary-nudge keyboard shortcuts.
- Added dependency-free possession-editor tests and a terse per-file code overview.
- Added a high-contrast current-frame possession badge that disappears in gaps, while selected-row emphasis remains independent for editing.
- Replaced separate new-possession controls with one context-sensitive button and the `N` key; `Escape` cancels pending creation.
- Replaced timeline placeholders with reusable complete-video and five-second-buffer detail timelines.
- Added current-frame, selected-possession, active-possession, gap, and overlap visuals plus click-to-seek/select behavior.
- Added cursor-centred wheel zoom, double-click fit, View-menu fit commands, and optional follow-current-frame behavior that defaults off.
- Added a tested new/active/no-possession interaction model with automatic no-seek selection handoff and gap retention for stretching.
- Made the start/end action state-specific: start in gaps, end pending creation, and disabled inside an existing possession.
- Kept the blue interaction badge visible as “CREATING NEW POSSESSION” throughout pending creation.
- Added a compact keyboard-shortcut reference below the action buttons.
- Centered the detail timeline on current frame during pending creation and added a colored tentative-range preview.

### Pending verification

- Verify H.264 and AV1 playback on Windows.
- Verify resize, focus, frame stepping, and shutdown on Linux/X11.
- Measure CPU, memory, and responsiveness with representative long videos.
- Compare displayed frame numbers against vision-pipeline frame numbers on representative videos.
- Measure first-load indexing time for H.264 and AV1, then verify cached reload speed.
- Verify the complete possession-editing and keyboard workflow in the user-managed PySide6 environment.

### Not started

- Packaging.

### Environment note

The current workspace environment has Python 3.7.5 and does not contain PySide6 or python-mpv. No packages were installed, per project coding rules; only dependency-free checks are run here.
