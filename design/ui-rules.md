# UI Rules

## Language

- Use **current frame**, **current possession**, **possession start**, and **possession end**.
- Do not use playhead, mark, In, or Out.
- Use operator-oriented actions: **Start a new possession**, **End current possession**, **Move active possession start here**, **Move active possession end here**, **Split**, and **Join**. Put exact mechanics and shortcuts in tooltips.
- Current possession means the editing target. Entering an existing possession makes it current without seeking; entering a gap retains the previous target for stretching.

## Layout

- Use three columns: possession list, video/timelines, current-possession details and actions.
- Keep the possession list and action panel on opposite sides of the video.
- Make both side panels resizable and collapsible.
- Keep the primary screen minimal; move export, settings, global validation, optional work boundaries, and help into menus.
- Optimize for 1366×768 at Windows display scaling up to 150%.

## Timelines

- Provide a thin overview timeline for the complete video.
- Provide a detail timeline showing the current possession with a small buffer on each side.
- Show a clear current-frame line on both timelines.
- During new-possession creation, keep the detail timeline centered around current frame and preview the tentative inclusive range with a colored bar.
- Show a green border around the video and a green current-possession label while creating a new possession; use blue for an existing active possession.
- Distinguish the current possession from the possession containing the current frame.
- Show gaps neutrally and overlaps as errors.
- Support fit-to-video, fit-current-possession, cursor-centred zoom, and optional follow-current-frame behaviour.
- Use the mouse wheel for cursor-centred zoom, double-click for context fit, and keep explicit fit/follow controls in the View menu.

## Current possession

- Focus status and validation on the current possession.
- Show start/end frame as primary values and timestamps as derived, read-only values.
- Show duration in frames and time.
- Show nearby gaps and overlap warnings concisely.
- Disable actions that are not currently valid.

## Interaction

- Timeline click selects a possession and moves to the clicked frame; clicking a gap clears selection.
- Entering another existing possession switches the current editing target without seeking; traversing into a gap retains it for boundary stretching.
- Creation uses one context-sensitive button and the `N` key: start at the current frame, navigate, then use the same action to end at the current frame. `Escape` cancels.
- Confirm deletion and reject overlaps.
- Disable global shortcuts while editing text.
- Show shortcuts in action-button tooltips.

## Visual design

- Prioritize video and the detail timeline.
- Use text labels for editing actions and familiar icons only for playback.
- Avoid duplicate controls, persistent dashboards, and status-icon clutter.
- Do not present valid gaps as reduced quality or failed coverage.
- Keep save state and frame-index loading/error state visible but unobtrusive.
- With native libmpv `wid`, put Qt status outside the video or use mpv OSD.
