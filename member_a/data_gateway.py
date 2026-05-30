"""Placeholder gateway for member C data tools.

Member C's real SQLite MCP and RAG tool names are intentionally blank in the PRD.
This gateway gives member A stable behavior now and a narrow replacement point later.
"""

from __future__ import annotations

from collections.abc import Iterable

from .mock_data import DATA_RECORDS
from .models import DataRecord


class TravelDataGateway:
    def __init__(self, records: Iterable[DataRecord] = DATA_RECORDS):
        self._records = tuple(records)

    def search(self, *, cities: tuple[str, ...], tags: tuple[str, ...]) -> list[DataRecord]:
        city_set = set(cities)
        tag_set = set(tags)
        return [
            record
            for record in self._records
            if record.is_structured
            and record.city in city_set
            and (not tag_set or tag_set.intersection(record.tags))
        ]

    def by_id(self, record_id: str) -> DataRecord:
        for record in self._records:
            if record.record_id == record_id:
                return record
        raise KeyError(record_id)

    def get_schedule_record(self, content: str) -> DataRecord | None:
        for record in self._records:
            if record.content == content:
                return record
        return None
