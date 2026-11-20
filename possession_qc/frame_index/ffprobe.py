"""ffprobe-backed exact frame-index provider."""

import json
import math
import subprocess
import threading
import time
from array import array
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from possession_qc.frame_index.model import FrameIndex, FrameIndexError
from possession_qc.frame_index.provider import (
    FrameIndexProgressCallback,
    FrameIndexProvider,
)


class FfprobeFrameIndexProvider(FrameIndexProvider):
    """Build a presentation-order frame index using FFmpeg's decoder."""

    def __init__(self, executable: str = "ffprobe") -> None:
        """Use ``executable`` as the ffprobe command name or absolute path."""
        self._executable = executable
        self._process_lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._cancel_requested = threading.Event()

    def build(
        self,
        video_path: Path,
        progress_callback: Optional[FrameIndexProgressCallback] = None,
    ) -> FrameIndex:
        """Stream decoded frame timestamps and report presentation-time progress."""
        self._cancel_requested.clear()
        numerator, denominator, duration = self._read_video_metadata(video_path)
        if self._cancel_requested.is_set():
            raise FrameIndexError("frame indexing was cancelled")
        if progress_callback is not None:
            progress_callback(0.0, duration)

        command = [
            self._executable,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp",
            "-of",
            "csv=p=0",
            str(video_path.resolve()),
        ]
        process = self._start_process(command)
        timestamps = array("q")
        first_timestamp: Optional[int] = None
        processed_seconds = 0.0
        last_progress_at = 0.0
        try:
            if process.stdout is None:
                raise FrameIndexError("could not read ffprobe frame output")
            for line in process.stdout:
                value = line.split(",", 1)[0].strip()
                if not value:
                    continue
                try:
                    timestamp = int(value)
                except ValueError as error:
                    raise FrameIndexError(
                        "could not parse ffprobe frame timestamp: %s" % value
                    ) from error
                timestamps.append(timestamp)
                if first_timestamp is None:
                    first_timestamp = timestamp
                processed_seconds = max(
                    0.0,
                    (timestamp - first_timestamp) * numerator / denominator,
                )
                now = time.monotonic()
                if progress_callback is not None and now - last_progress_at >= 0.2:
                    progress_callback(processed_seconds, duration)
                    last_progress_at = now
            stderr = process.stderr.read() if process.stderr is not None else ""
            return_code = process.wait()
        except Exception:
            if process.poll() is None:
                process.terminate()
            process.communicate()
            raise
        finally:
            self._clear_process(process)

        if return_code != 0:
            raise FrameIndexError(
                self._process_failure_message(
                    "frame timestamp query", command, return_code, stderr
                )
            )
        if progress_callback is not None:
            progress_callback(processed_seconds, duration)
        return FrameIndex(numerator, denominator, timestamps)

    def cancel(self) -> None:
        """Terminate the active ffprobe child process, if one exists."""
        self._cancel_requested.set()
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    def _read_video_metadata(self, video_path: Path) -> Tuple[int, int, float]:
        """Read the selected stream time base and container duration quickly."""
        command = [
            self._executable,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=time_base,duration:format=duration",
            "-of",
            "json",
            str(video_path.resolve()),
        ]
        process = self._start_process(command)
        try:
            stdout, stderr = process.communicate()
        finally:
            self._clear_process(process)
        if process.returncode != 0:
            raise FrameIndexError(
                self._process_failure_message(
                    "metadata query", command, process.returncode, stderr
                )
            )
        try:
            output = json.loads(stdout)
            numerator, denominator = self._read_time_base(output)
            duration = self._read_duration(output)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise FrameIndexError("could not parse ffprobe metadata: %s" % error)
        return numerator, denominator, duration

    def _start_process(self, command: List[str]) -> subprocess.Popen:
        """Start and register an ffprobe child process for cancellation."""
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creation_flags,
            )
        except OSError as error:
            raise FrameIndexError(
                "Could not start ffprobe for %s: %s: %s"
                % (command[-1], error.__class__.__name__, error)
            ) from error
        with self._process_lock:
            self._process = process
        return process

    def _clear_process(self, process: subprocess.Popen) -> None:
        """Clear ``process`` if it is still the registered active child."""
        with self._process_lock:
            if self._process is process:
                self._process = None

    def _process_failure_message(
        self, stage: str, command: List[str], return_code: int, stderr: str
    ) -> str:
        """Describe a failed ffprobe command with usable operator diagnostics."""
        output = stderr.strip() or "ffprobe produced no diagnostic output"
        return (
            "ffprobe %s failed with exit code %d.\n"
            "Command: %s\n"
            "ffprobe output: %s"
            % (stage, return_code, " ".join(command), output)
        )

    def _read_time_base(self, output: Dict[str, Any]) -> Tuple[int, int]:
        """Read the selected video stream's rational timestamp time base."""
        streams = output["streams"]
        if not isinstance(streams, list) or len(streams) != 1:
            raise ValueError("expected one selected video stream")
        time_base = streams[0]["time_base"]
        numerator_text, denominator_text = str(time_base).split("/", 1)
        numerator = int(numerator_text)
        denominator = int(denominator_text)
        if numerator <= 0 or denominator <= 0:
            raise ValueError("video stream has an invalid time base")
        return numerator, denominator

    def _read_duration(self, output: Dict[str, Any]) -> float:
        """Read a finite positive duration, preferring the selected stream."""
        streams = output["streams"]
        format_data = output.get("format", {})
        candidates = [streams[0].get("duration"), format_data.get("duration")]
        for candidate in candidates:
            try:
                duration = float(candidate)
            except (TypeError, ValueError):
                continue
            if math.isfinite(duration) and duration > 0:
                return duration
        raise ValueError("video duration is unavailable")
