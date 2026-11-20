# Possession QC Tool

Desktop tool for correcting basketball possession mappings.

## Development setup

Use Python 3.10 or newer in a dedicated virtual environment, then install `requirements.txt`. libmpv must also be available to the application as `mpv-2.dll` on Windows or `libmpv.so` on Linux. The `ffprobe` executable must be available on `PATH` to build exact frame indexes.

Linux is currently supported through X11. Under a Wayland session, launch Qt with its X11 backend:

```bash
QT_QPA_PLATFORM=xcb python main.py
```

Run the application with:

```bash
python main.py
```

The first load of a video builds a decoded-frame timestamp index in the background and caches it beside the video as `<video>.possession-qc-index.json`. Long AV1 videos can take time on their first load; later loads use the fingerprint-validated cache.

Run dependency-free tests with:

```bash
python -m unittest discover -s tests
```
