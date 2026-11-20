# High-Level Design

```text
PySide6 UI
  ├── Video View ────── VideoPlayer interface ─── libmpv wid backend
  ├── Timeline
  ├── Possession List
  └── Status/Commands
             │
        App Controller
       ┌─────┼─────────┐
Interaction State  Possession Editor   FrameIndex service
       │                 │
Validation         FrameIndexProvider
       │            ├── Pipeline sidecar
MappingRepository   └── ffprobe fallback
       │
JSON + 5 backups
```

## Components

- **App Controller:** Coordinates UI, playback, selection, editing, and saving.
- **VideoPlayer:** Loads, plays, pauses, seeks, steps, and exposes presentation time.
- **FrameIndex:** Converts exact frame numbers to/from presentation timestamps.
- **Possession Editor:** Implements create, delete, split, join, stretch, and shrink.
- **Interaction State:** Derives new, active, or no-possession context and selection handoff from current frame.
- **Validator:** Detects overlaps and provides future validation stubs.
- **MappingRepository:** Loads/saves JSON and rotates five backups.
- **Timeline:** Displays possessions, gaps, selection, current frame, and zoom.
- **Command/Keymap:** Maps keyboard and UI actions to editor commands.
- **Background Worker:** Builds frame indexes without blocking the UI.

## Replaceable boundaries

| Interface | Initial implementation | Future replacement |
|---|---|---|
| `VideoPlayer` | libmpv native `wid` | libmpv render API or pipeline player |
| `FrameIndexProvider` | Pipeline sidecar / ffprobe | Pipeline-native frame service |
| `MappingRepository` | Local JSON files | Existing correction-tool storage |
| `MappingCodec` | Initial JSON schema | Final pipeline schema |
| `Command/Keymap` | Hard-coded defaults | User-configurable bindings |

The domain model and possession-editing logic remain independent of Qt and libmpv so they can later move into the larger correction tool.
