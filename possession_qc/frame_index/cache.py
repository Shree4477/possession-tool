"""Fingerprint-validated frame-index sidecar cache."""

import hashlib
import json
import os
import tempfile
from array import array
from pathlib import Path
from typing import Any, Dict, Optional

from possession_qc.frame_index.model import FrameIndex, FrameIndexError


class FrameIndexCache:
    """Store compact frame indexes beside videos and reject stale entries."""

    _format_version = 1
    _hash_chunk_size = 65_536

    def path_for_video(self, video_path: Path) -> Path:
        """Return the sidecar path used for ``video_path``."""
        return video_path.with_name("%s.possession-qc-index.json" % video_path.name)

    def load(self, video_path: Path) -> Optional[FrameIndex]:
        """Load a cached index only when its video fingerprint still matches."""
        cache_path = self.path_for_video(video_path)
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            if payload.get("version") != self._format_version:
                return None
            if payload.get("video") != self._fingerprint(video_path):
                return None
            time_base = payload["time_base"]
            timestamps = array("q", payload["timestamps"])
            return FrameIndex(int(time_base[0]), int(time_base[1]), timestamps)
        except (OSError, KeyError, TypeError, ValueError, FrameIndexError):
            return None

    def save(self, video_path: Path, frame_index: FrameIndex) -> None:
        """Atomically cache ``frame_index`` with its source video fingerprint."""
        cache_path = self.path_for_video(video_path)
        payload = {
            "version": self._format_version,
            "video": self._fingerprint(video_path),
            "time_base": [
                frame_index.time_base_numerator,
                frame_index.time_base_denominator,
            ],
            "timestamps": list(frame_index.timestamps),
        }
        serialized = json.dumps(payload, separators=(",", ":"))
        descriptor, filename = tempfile.mkstemp(
            prefix=".%s." % cache_path.name,
            suffix=".tmp",
            dir=str(cache_path.parent),
            text=True,
        )
        temporary_path = Path(filename)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(str(temporary_path), str(cache_path))
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def _fingerprint(self, video_path: Path) -> Dict[str, Any]:
        """Fingerprint file identity using metadata and bounded content reads."""
        stat = video_path.stat()
        digest = hashlib.sha256()
        with video_path.open("rb") as stream:
            digest.update(stream.read(self._hash_chunk_size))
            if stat.st_size > self._hash_chunk_size:
                stream.seek(max(0, stat.st_size - self._hash_chunk_size))
                digest.update(stream.read(self._hash_chunk_size))
        return {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "sample_sha256": digest.hexdigest(),
        }

