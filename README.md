# 🏀 Basketball Possession QC Tool

A frame-accurate quality control application for basketball match possessions.

🌐 **Live Web Application (No installation or cloning needed):**  
**[https://shree4477.github.io/possession-tool/](https://shree4477.github.io/possession-tool/)**

---

## 🌟 Features

- **100% In-Browser & Client-Side**: No software, Python, or Git installation required. Zero video uploads to external servers; your match video and JSON remain strictly private and local.
- **Dual Frame-Accurate Timelines**:
  - **Overview Timeline**: Complete match overview with possession blocks and interactive scrubbing.
  - **Detail Timeline**: Zoomable (mouse wheel) and pannable frame-by-frame view with buffer and live boundary adjustments.
- **Context-Aware Visual Feedback**:
  - 🟢 **Green Border**: Creating a new possession (`N`).
  - 🔵 **Blue Border**: Current frame is within an active possession.
  - ⚪ **Neutral**: In a gap between possessions.
- **Full Operator Editing Workflow**:
  - **Create (`N`)**: Mark start and end frames with automatic numbering.
  - **Split (`S`)**: Split an active possession at the current frame.
  - **Join (`J` / `Shift+J`)**: Merge with following or previous possession.
  - **Stretch Boundaries (`[` / `]`)**: Move start or end boundary to current frame.
  - **Delete (`Delete`)**: Remove possession and renumber.
- **Built-in Interactive Demo**: Click **Open → Load sample demo** to immediately try all features with a simulated court video and sample possessions.
- **Desktop Version**: Python + PySide6 (Qt) + MPV engine is also available in this repository for local high-throughput desktop pipelines.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Space` | Play / Pause |
| `←` / `→` | Step −1 / +1 frame |
| `Shift + ←` / `Shift + →` | Seek −1 / +1 second |
| `Ctrl + ←` / `Ctrl + →` | Seek −1 / +1 minute |
| `↑` / `↓` | Select previous / next possession |
| `N` | Start / end new possession |
| `S` | Split active possession at current frame |
| `J` / `Shift + J` | Join next / previous possession |
| `[` / `]` | Move active possession start / end here |
| `Delete` | Delete active possession |
| `Home` / `End` | Jump to possession start / end |
| `Esc` | Cancel creation / Clear selection |
| `Ctrl + S` | Save / Export JSON mapping |
| `Ctrl + 0` | Fit complete overview timeline to video |
| `Ctrl + 1` | Fit detail timeline to current possession |

---

## 💻 Running the Desktop App (Optional)

If you prefer running the Python Qt desktop version locally:

1. Install Python 3.10+ and requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Ensure `mpv-2.dll` (Windows) or `libmpv.so` (Linux) and `ffprobe` are on `PATH`.
3. Launch:
   ```bash
   python main.py
   ```
4. Run tests:
   ```bash
   python -m unittest discover -s tests
   ```

---

## 📄 License
MIT License
