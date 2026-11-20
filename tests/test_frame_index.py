"""Tests for exact frame timestamp indexing and caching."""

import tempfile
import unittest
from array import array
from pathlib import Path
from typing import Optional

from possession_qc.frame_index import (
    FrameIndex,
    FrameIndexCache,
    FrameIndexError,
    FrameIndexProvider,
    FrameIndexService,
)
from possession_qc.frame_index.ffprobe import FfprobeFrameIndexProvider
from possession_qc.frame_index.provider import FrameIndexProgressCallback


class StubFrameIndexProvider(FrameIndexProvider):
    """Return a fixed index while recording provider usage."""

    def __init__(self, frame_index: FrameIndex) -> None:
        """Create the stub with the index returned by every build."""
        self.frame_index = frame_index
        self.build_count = 0
        self.cancel_count = 0

    def build(
        self,
        video_path: Path,
        progress_callback: Optional[FrameIndexProgressCallback] = None,
    ) -> FrameIndex:
        """Return the configured index and increment the build count."""
        self.build_count += 1
        if progress_callback is not None:
            progress_callback(2.0, 3.0)
        return self.frame_index

    def cancel(self) -> None:
        """Record a cancellation request."""
        self.cancel_count += 1


class FrameIndexTests(unittest.TestCase):
    """Verify VFR-safe lookup and frame-index invariants."""

    def test_maps_variable_timestamps_without_fps_math(self) -> None:
        """Resolve frames using their individual presentation timestamps."""
        frame_index = FrameIndex(1, 100, array("q", [100, 140, 220, 225]))

        self.assertEqual(frame_index.timestamp_seconds(0), 0.0)
        self.assertEqual(frame_index.timestamp_seconds(2), 1.2)
        self.assertEqual(frame_index.frame_for_seconds(0.39), 1)
        self.assertEqual(frame_index.frame_for_seconds(1.24), 3)

    def test_uses_inclusive_zero_based_frame_numbers(self) -> None:
        """Expose the first and final decoded frames by zero-based number."""
        frame_index = FrameIndex(1, 10, array("q", [5, 6, 9]))

        self.assertEqual(frame_index.frame_count, 3)
        self.assertEqual(frame_index.timestamp_seconds(2), 0.4)
        with self.assertRaises(IndexError):
            frame_index.timestamp_seconds(3)

    def test_rejects_duplicate_timestamps(self) -> None:
        """Reject timestamps that cannot identify one exact decoded frame."""
        with self.assertRaisesRegex(FrameIndexError, "duplicate or non-monotonic"):
            FrameIndex(1, 1000, array("q", [0, 40, 40]))

    def test_cache_invalidates_when_video_changes(self) -> None:
        """Ignore a sidecar when bounded video fingerprint data changes."""
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "match.mp4"
            video_path.write_bytes(b"first video content")
            cache = FrameIndexCache()
            frame_index = FrameIndex(1, 100, array("q", [0, 4, 9]))
            cache.save(video_path, frame_index)

            self.assertIsNotNone(cache.load(video_path))
            video_path.write_bytes(b"different video content and size")
            self.assertIsNone(cache.load(video_path))

    def test_service_builds_once_then_uses_cache(self) -> None:
        """Build an uncached index once and resolve subsequent calls from cache."""
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "match.mp4"
            video_path.write_bytes(b"video fixture")
            frame_index = FrameIndex(1, 100, array("q", [0, 4, 9]))
            provider = StubFrameIndexProvider(frame_index)
            service = FrameIndexService(provider, FrameIndexCache())

            first = service.get_or_build(video_path)
            second = service.get_or_build(video_path)

            self.assertFalse(first.from_cache)
            self.assertTrue(second.from_cache)
            self.assertEqual(provider.build_count, 1)

    def test_service_forwards_provider_progress(self) -> None:
        """Forward exact processed and total seconds during an uncached build."""
        with tempfile.TemporaryDirectory() as directory:
            video_path = Path(directory) / "match.mp4"
            video_path.write_bytes(b"video fixture")
            provider = StubFrameIndexProvider(
                FrameIndex(1, 100, array("q", [0, 4, 9]))
            )
            service = FrameIndexService(provider, FrameIndexCache())
            progress = []

            service.get_or_build(
                video_path,
                lambda processed, total: progress.append((processed, total)),
            )

            self.assertEqual(progress, [(2.0, 3.0)])

    def test_ffprobe_failure_identifies_the_stage_and_command(self) -> None:
        """Keep enough ffprobe context to diagnose a failed Windows process."""
        provider = FfprobeFrameIndexProvider()

        message = provider._process_failure_message(
            "metadata query", ["ffprobe", "C:/video/match.mp4"], 1, "bad input"
        )

        self.assertIn("metadata query", message)
        self.assertIn("exit code 1", message)
        self.assertIn("ffprobe C:/video/match.mp4", message)
        self.assertIn("bad input", message)
