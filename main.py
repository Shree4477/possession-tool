"""Application entry point for the Possession QC Tool."""

import os
import sys
from pathlib import Path

# Ensure local DLLs (mpv-2.dll) and binaries are discoverable on Windows
_project_dir = str(Path(__file__).resolve().parent)
if _project_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _project_dir + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(_project_dir)
    except OSError:
        pass

from possession_qc.application import run


def main() -> int:
    """Start the desktop application and return its process exit code."""
    return run()


if __name__ == "__main__":
    raise SystemExit(main())

