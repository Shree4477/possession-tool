"""Tests for the temporary possession mapping schema."""

import json
import unittest

from possession_qc.domain import Possession
from possession_qc.mapping import PossessionMappingCodec


class PossessionMappingCodecTests(unittest.TestCase):
    """Verify typed decoding, validation, and unknown-field preservation."""

    def test_decodes_assumed_schema(self) -> None:
        """Decode hyphenated JSON fields into a possession dataclass."""
        codec = PossessionMappingCodec()

        possessions = codec.decode(
            '[{"possession-num": 1, "start-frame": 10, "start-time": 0.4, '
            '"end-frame": 20, "end-time": 0.8}]'
        )

        self.assertEqual(
            possessions,
            [Possession(1, 10, 0.4, 20, 0.8)],
        )
        self.assertEqual(possessions[0].duration_frames, 11)

    def test_preserves_unknown_fields_during_round_trip(self) -> None:
        """Retain pipeline additions that are not yet represented in the model."""
        codec = PossessionMappingCodec()
        source = [
            {
                "possession-num": 4,
                "start-frame": 100,
                "start-time": 3.25,
                "end-frame": 140,
                "end-time": 4.5,
                "pipeline-note": {"confidence": 0.91},
            }
        ]

        encoded = codec.encode(codec.decode(json.dumps(source)))

        self.assertEqual(json.loads(encoded), source)

    def test_rejects_non_list_root(self) -> None:
        """Reject mappings that do not use the assumed top-level list."""
        with self.assertRaisesRegex(ValueError, "root must be a list"):
            PossessionMappingCodec().decode("{}")

    def test_rejects_reversed_frame_range(self) -> None:
        """Reject possessions whose inclusive end precedes their start."""
        serialized = (
            '[{"possession-num": 1, "start-frame": 20, "start-time": 0.4, '
            '"end-frame": 10, "end-time": 0.8}]'
        )

        with self.assertRaisesRegex(ValueError, "end_frame cannot precede"):
            PossessionMappingCodec().decode(serialized)

    def test_rejects_boolean_frame(self) -> None:
        """Reject JSON booleans even though bool subclasses int in Python."""
        serialized = (
            '[{"possession-num": 1, "start-frame": true, "start-time": 0.4, '
            '"end-frame": 10, "end-time": 0.8}]'
        )

        with self.assertRaisesRegex(ValueError, "start-frame must be an integer"):
            PossessionMappingCodec().decode(serialized)
