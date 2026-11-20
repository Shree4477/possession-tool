"""Tests for schema-neutral JSON mapping persistence."""

import json
import tempfile
import unittest
from pathlib import Path

from possession_qc.mapping import MappingRepository


class MappingRepositoryTests(unittest.TestCase):
    """Verify lossless schema handling and bounded backup rotation."""

    def test_loads_unknown_json_structure(self) -> None:
        """Load nested fields without requiring a possession schema."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            expected = {"future_field": {"nested": [1, True, None]}, "possessions": []}
            path.write_text(json.dumps(expected), encoding="utf-8")

            document = MappingRepository().load(path)

            self.assertEqual(document.data, expected)
            self.assertFalse(document.dirty)

    def test_new_document_does_not_create_its_file_until_saved(self) -> None:
        """Keep a new empty mapping in memory until the operator saves it."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            repository = MappingRepository()

            document = repository.new_document(path, [])

            self.assertEqual(document.path, path)
            self.assertEqual(document.data, [])
            self.assertFalse(document.dirty)
            self.assertFalse(path.exists())

            repository.save(document)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [])

    def test_save_creates_backup_and_marks_document_clean(self) -> None:
        """Keep the pre-save file as generation one and clear dirty state."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            path.write_text('{"version": 1}\n', encoding="utf-8")
            repository = MappingRepository()
            document = repository.load(path)
            document.data["version"] = 2
            document.mark_dirty()

            repository.save(document)

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"version": 2})
            self.assertEqual(
                json.loads(repository.backup_path(path, 1).read_text(encoding="utf-8")),
                {"version": 1},
            )
            self.assertFalse(document.dirty)

    def test_retains_only_five_previous_versions(self) -> None:
        """Rotate backups so generations one through five are newest to oldest."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "match.json"
            path.write_text('{"version": 1}\n', encoding="utf-8")
            repository = MappingRepository()
            document = repository.load(path)

            for version in range(2, 8):
                document.data["version"] = version
                document.mark_dirty()
                repository.save(document)

            backup_versions = [
                json.loads(
                    repository.backup_path(path, generation).read_text(encoding="utf-8")
                )["version"]
                for generation in range(1, 6)
            ]
            self.assertEqual(backup_versions, [6, 5, 4, 3, 2])
            self.assertFalse(Path("%s.bak6" % path).exists())

    def test_rejects_invalid_json(self) -> None:
        """Expose invalid input without replacing it or creating backups."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{broken", encoding="utf-8")

            with self.assertRaises(ValueError):
                MappingRepository().load(path)
