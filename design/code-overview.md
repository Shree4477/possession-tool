# Code Overview

## Entry and shared utilities

| File | Important symbols | Changes that belong here |
|---|---|---|
| `main.py` | `main()` | Process entrypoint only; delegate application setup elsewhere. |
| `possession_qc/application.py` | `run()` | Qt application creation, application-wide metadata, and main-window startup. |
| `possession_qc/timecode.py` | `format_timestamp()` | Shared presentation-time formatting and parsing helpers. |
| `possession_qc/__init__.py` | Package marker | Package-level metadata only. |

## Domain and JSON mapping

| File | Important symbols | Changes that belong here |
|---|---|---|
| `domain/possession.py` | `Possession`, `duration_frames` | Possession fields and schema-independent invariants such as inclusive frame ranges. |
| `domain/editor.py` | `PossessionEditor`, `PossessionEditResult`, `PossessionEditError` | Create/delete/split/join/boundary rules, overlap rejection, ordering, and renumbering. |
| `domain/interaction.py` | `InteractionMode`, `InteractionState`, `resolve_interaction_state()` | Derive new, active, or no-possession UI context from current frame and pending creation. |
| `domain/__init__.py` | Domain exports | Public possession and editor API exports. |
| `mapping/model.py` | `MappingDocument`, `mark_dirty()`, `mark_clean()` | Loaded-document state, source path, and unsaved-change tracking. |
| `mapping/codec.py` | `MappingCodec`, `JsonMappingCodec`, `PossessionMappingCodec` | JSON schema parsing/serialization, field validation, and unknown-field preservation. |
| `mapping/repository.py` | `MappingRepository`, `load()`, `save()` | File I/O, atomic replacement, and five-generation backup rotation. |
| `mapping/__init__.py` | Mapping exports | Public mapping API exports. |

## Exact frame indexing

| File | Important symbols | Changes that belong here |
|---|---|---|
| `frame_index/model.py` | `FrameIndex`, `FrameIndexError`, `timestamp_seconds()`, `frame_for_seconds()` | Exact frame/PTS representation, lookup rules, and timestamp invariants. Never add FPS-based mapping here. |
| `frame_index/provider.py` | `FrameIndexProvider`, `FrameIndexProgressCallback` | Replaceable index-provider contract, including cancellation and progress semantics. |
| `frame_index/ffprobe.py` | `FfprobeFrameIndexProvider`, `build()` | ffprobe commands, streamed timestamp extraction, duration discovery, progress, and process cancellation. |
| `frame_index/cache.py` | `FrameIndexCache`, `load()`, `save()` | Adjacent sidecar format, video fingerprinting, cache validation, and cache persistence. |
| `frame_index/service.py` | `FrameIndexService`, `FrameIndexResult`, `get_or_build()` | Cache-first orchestration and provider selection; no UI logic. |
| `frame_index/__init__.py` | Frame-index exports | Public frame-index API exports. |

## Video playback

| File | Important symbols | Changes that belong here |
|---|---|---|
| `player/base.py` | `VideoPlayer` | Backend-neutral playback contract: load, play/pause, seek, step, and close. |
| `player/mpv_native.py` | `NativeMpvPlayer` | libmpv options, native `wid` embedding, property observation, and mpv command translation. |
| `player/__init__.py` | Player exports | Public playback API exports. |

## Qt UI

| File | Important symbols | Changes that belong here |
|---|---|---|
| `ui/main_window.py` | `MainWindow` | Window composition, menus, shortcuts, dialogs, selection wiring, UI state refresh, and coordination of player/mapping/index services. Move reusable widgets or growing business rules out of this file. |
| `ui/frame_index_worker.py` | `FrameIndexWorker`, `progress`, `completed`, `failed` | Qt-thread adapter for index services and delivery of worker results to the UI thread. |
| `ui/timeline.py` | `PossessionTimeline`, `set_state()`, `frame_clicked` | Reusable overview/detail painting, current-frame and selection indicators, overlap display, and exact click-to-frame mapping. |
| `ui/__init__.py` | Package marker | Public UI exports if reusable widgets are introduced. |

## Tests

| File | Coverage focus | Add tests here for |
|---|---|---|
| `tests/test_timecode.py` | Time formatting | Timestamp formatting/parsing edge cases. |
| `tests/test_possession_codec.py` | Possession JSON schema | Decode/encode validation, round trips, and added schema fields. |
| `tests/test_possession_editor.py` | Possession editing | Inclusive create/delete/split/join/boundary operations, overlaps, and renumbering. |
| `tests/test_interaction.py` | Interaction states | New/active/no-possession resolution and precedence. |
| `tests/test_mapping_repository.py` | Persistence | Atomic saves, dirty state, malformed JSON, and backup rotation. |
| `tests/test_frame_index.py` | Exact frame mapping | PTS lookup, VFR behavior, cache validity, provider progress, and service orchestration. |
| `tests/__init__.py` | Test package marker | No implementation logic. |

## Placement rule

Keep possession rules in `domain`, serialization in `mapping`, exact frame knowledge in `frame_index`, playback commands in `player`, and Qt-only behavior in `ui`. Cross-layer workflow coordination currently belongs in `MainWindow`; extract an application service when possession editing makes that coordination substantial.
