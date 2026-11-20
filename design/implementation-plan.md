# Iterative Implementation Plan

Each iteration must end with a runnable application. Add focused automated tests for domain, persistence, validation, and frame-mapping logic as those components are introduced.

## 1. Technical spike

- Build a minimal PySide6 window with native libmpv `wid` embedding.
- Load representative H.264 and AV1 videos; verify play, pause, seek, frame-step, resize, and shutdown on Windows and Linux/X11.
- Measure startup time, responsiveness, CPU, and memory before committing to the backend.

## 2. Application skeleton

- Create the three-column, resizable layout with placeholder video, list, timeline, and action panels.
- Add video/JSON loading, domain models, a replaceable JSON codec, dirty-state tracking, close confirmation, and five-backup save rotation.
- Keep Qt, persistence, and domain logic in separate modules from the start.

## 3. Exact frame navigation

- Introduce the `FrameIndex` abstraction with a cached ffprobe-based provider and a future pipeline-sidecar provider.
- Display current frame and derived time; implement seek-to-frame and verified forward/backward frame stepping.
- Block interaction with an application-modal progress dialog while each video's index is loaded or built; stream decoded presentation-time progress against total video duration without estimating frames from FPS.
- Detect missing, duplicate, or invalid timestamps and surface indexing failures without freezing the UI.

## 4. Possession workflow

- Implement the possession list and explicit current-possession selection without automatic selection changes during playback.
- Add create, delete, split, join, and set-possession-start/end-to-current-frame operations.
- Add agreed keyboard shortcuts, overlap rejection, renumbering, and unit tests for inclusive boundaries.
- Clearly distinguish the active possession in both the list and action panel.
- Replace separate start/end-new-possession controls with one context-sensitive button and shortcut that starts, then ends, a possession.
- Decide what the context-sensitive start/end button should display or do while current frame is inside an existing possession.

## 5. Timelines

- Add a thin complete-video overview timeline for navigation and a detailed current-possession timeline with surrounding buffer.
- Show the current frame, current possession, nearby possessions, gaps, overlaps, and editable boundaries clearly.
- Add fit-to-video, fit-current-possession, cursor-centred zoom, and optional follow-current-frame behaviour.

## 6. Current-possession status

- Show start/end frames as primary values, derived timestamps, duration, nearby gaps, and overlap warnings.
- Add validation stubs and keep global summaries or infrequent controls in menus.
- Disable actions that are invalid for the current selection or frame.
- During `NEW_POSSESSION`, keep the blue status badge visible and show that a new possession is being created.
- Show a compact keyboard-shortcut reference below the action-button panel.

## 7. Hardening and delivery

- Test 90-minute to 3-hour videos, 720p/1080p content, large JSON files, malformed inputs, and video/JSON mismatches.
- Verify the layout at 1366×768 and Windows scaling up to 150%, then test Linux/X11 compatibility.
- Produce a Windows-first runnable package or simple development setup, plus concise Linux/X11 setup instructions.
