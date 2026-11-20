"""Atomic local-file persistence with rotating mapping backups."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from possession_qc.mapping.codec import JsonMappingCodec, MappingCodec
from possession_qc.mapping.model import MappingDocument


class MappingRepository:
    """Load and safely update mapping files while retaining prior copies."""

    def __init__(
        self, codec: Optional[MappingCodec] = None, backup_count: int = 5
    ) -> None:
        """Create a repository using ``codec`` and a fixed backup history size."""
        if backup_count < 0:
            raise ValueError("backup_count cannot be negative")
        self._codec = codec if codec is not None else JsonMappingCodec()
        self._backup_count = backup_count

    def load(self, path: Path) -> MappingDocument:
        """Load and decode a mapping document from ``path``."""
        serialized = path.read_text(encoding="utf-8")
        return MappingDocument(path=path, data=self._codec.decode(serialized))

    def new_document(self, path: Path, data: Any) -> MappingDocument:
        """Create an unsaved mapping document without writing ``path``."""
        return MappingDocument(path=path, data=data)

    def save(self, document: MappingDocument) -> None:
        """Atomically save ``document`` after rotating its previous five copies."""
        serialized = self._codec.encode(document.data)
        document.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._write_temporary(document.path, serialized)

        try:
            self._rotate_backups(document.path)
            if self._backup_count and document.path.exists():
                shutil.copy2(document.path, self.backup_path(document.path, 1))
            os.replace(str(temporary_path), str(document.path))
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        document.mark_clean()

    def backup_path(self, path: Path, generation: int) -> Path:
        """Return the adjacent backup filename for a one-based generation."""
        if generation < 1 or generation > self._backup_count:
            raise ValueError("backup generation is outside configured history")
        return Path("%s.bak%d" % (path, generation))

    def _rotate_backups(self, path: Path) -> None:
        """Shift existing backups toward the oldest retained generation."""
        for generation in range(self._backup_count, 1, -1):
            source = self.backup_path(path, generation - 1)
            destination = self.backup_path(path, generation)
            if source.exists():
                os.replace(str(source), str(destination))

    def _write_temporary(self, target: Path, serialized: str) -> Path:
        """Write and flush serialized mapping data beside its final target."""
        descriptor, filename = tempfile.mkstemp(
            prefix=".%s." % target.name,
            suffix=".tmp",
            dir=str(target.parent),
            text=True,
        )
        temporary_path = Path(filename)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(serialized)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            if temporary_path.exists():
                temporary_path.unlink()
            raise
        return temporary_path
