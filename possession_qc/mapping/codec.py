"""Replaceable mapping serialization formats."""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from possession_qc.domain import Possession


class MappingCodec(ABC):
    """Translate between serialized text and schema-neutral mapping data."""

    @abstractmethod
    def decode(self, serialized: str) -> Any:
        """Decode mapping text into an in-memory JSON-compatible value."""

    @abstractmethod
    def encode(self, data: Any) -> str:
        """Encode mapping data as text suitable for an atomic file update."""


class JsonMappingCodec(MappingCodec):
    """Preserve arbitrary JSON fields until the pipeline schema is known."""

    def decode(self, serialized: str) -> Any:
        """Decode a JSON mapping without imposing a possession schema."""
        return json.loads(serialized)

    def encode(self, data: Any) -> str:
        """Encode mapping data as deterministic, human-readable JSON."""
        return json.dumps(
            data,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=False,
        ) + "\n"


class PossessionMappingCodec(MappingCodec):
    """Translate the temporary possession-list JSON schema to domain models."""

    _required_fields = (
        "possession-num",
        "start-frame",
        "start-time",
        "end-frame",
        "end-time",
    )

    def __init__(self) -> None:
        """Create the schema codec using the generic JSON text codec."""
        self._json_codec = JsonMappingCodec()

    def decode(self, serialized: str) -> List[Possession]:
        """Decode and validate the assumed top-level possession list."""
        raw_data = self._json_codec.decode(serialized)
        if not isinstance(raw_data, list):
            raise ValueError("mapping JSON root must be a list")

        possessions = []
        for index, raw_possession in enumerate(raw_data):
            if not isinstance(raw_possession, dict):
                raise ValueError("possession at index %d must be an object" % index)
            try:
                possessions.append(self._decode_possession(raw_possession))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("invalid possession at index %d: %s" % (index, error))
        return possessions

    def encode(self, data: Any) -> str:
        """Encode typed possessions while preserving their unknown fields."""
        if not isinstance(data, list):
            raise TypeError("possession mapping data must be a list")

        raw_possessions = []
        for index, possession in enumerate(data):
            if not isinstance(possession, Possession):
                raise TypeError("mapping item at index %d is not a Possession" % index)
            raw_possessions.append(self._encode_possession(possession))
        return self._json_codec.encode(raw_possessions)

    def _decode_possession(self, raw: Dict[str, Any]) -> Possession:
        """Decode one JSON object into a validated possession model."""
        extra_fields = {
            key: value for key, value in raw.items() if key not in self._required_fields
        }
        return Possession(
            possession_num=self._read_integer(raw, "possession-num"),
            start_frame=self._read_integer(raw, "start-frame"),
            start_time=self._read_number(raw, "start-time"),
            end_frame=self._read_integer(raw, "end-frame"),
            end_time=self._read_number(raw, "end-time"),
            extra_fields=extra_fields,
        )

    def _encode_possession(self, possession: Possession) -> Dict[str, Any]:
        """Encode one possession using the agreed hyphenated field names."""
        raw = dict(possession.extra_fields)
        raw.update(
            {
                "possession-num": possession.possession_num,
                "start-frame": possession.start_frame,
                "start-time": possession.start_time,
                "end-frame": possession.end_frame,
                "end-time": possession.end_time,
            }
        )
        return raw

    def _read_integer(self, raw: Dict[str, Any], field_name: str) -> int:
        """Read a required JSON integer while excluding booleans."""
        value = raw[field_name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("%s must be an integer" % field_name)
        return value

    def _read_number(self, raw: Dict[str, Any], field_name: str) -> float:
        """Read a required JSON number while excluding booleans."""
        value = raw[field_name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("%s must be a number" % field_name)
        return float(value)
