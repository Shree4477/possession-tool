# Design Choices

## Video: libmpv

- Use PySide6 Qt Widgets with libmpv native `wid` embedding.
- Target Windows and Linux/X11; require X11 for Linux initially.
- Hide playback behind an adapter so a render-API backend can replace `wid` for Wayland later.
- Disable audio and frame-changing filters.
- Frame number is the source of truth. Never derive it from FPS and time.
- Use libmpv `time-pos` as the current normalized presentation time, not `estimated-frame-number`.
- Map presentation time to frame number through a cached frame-to-PTS index, preferably produced by the vision pipeline; use ffprobe as fallback.

## Keyboard shortcuts

### Playback and selection

| Action | Key |
|---|---|
| Play/pause | `Space` |
| Previous/next frame | `Left` / `Right` |
| Previous/next second | `Shift+Left` / `Shift+Right` |
| Previous/next minute | `Ctrl+Left` / `Ctrl+Right` |
| Select previous/next possession and seek to start | `Up` / `Down` |
| Select possession under playhead | `Enter` |
| Clear selection/cancel | `Escape` |
| Jump to selected start/end | `Home` / `End` |

Entering an existing possession automatically makes it the selected editing target without seeking. Entering a gap retains the previous selection for stretching; entering another possession switches selection. Timeline click selects a possession and seeks to the clicked frame; clicking a gap clears selection.

### Editing

| Action | Key |
|---|---|
| Start/end new possession | `N` |
| Delete selected | `Delete` |
| Split before playhead | `S` |
| Join selected with next | `J` |
| Join selected with previous | `Shift+J` |
| Set selected start/end to playhead | `[` / `]` |

`N` starts a new possession at current frame when none is pending, then ends it at current frame. `Escape` cancels a pending creation. Use `[` and `]` to move a boundary toward the possession to shrink it or away from it to stretch it. Confirm deletion, reject overlaps, and disable shortcuts while editing text.

## Temporary mapping schema

The JSON root is a list of possession objects with `possession-num`, `start-frame`, `start-time`, `end-frame`, and `end-time`. Frame ranges are zero-indexed and inclusive; frame numbers are authoritative. Unknown fields are preserved during load/save.
