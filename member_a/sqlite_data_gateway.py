"""SQLite-backed data gateway for member C's full DATA_FINAL database."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cached_property
from pathlib import Path
import re
import sqlite3
from typing import Any

from .models import DataRecord


class SQLiteTravelDataGateway:
    """Read member C's SQLite database through member A's gateway interface."""

    prefers_search_results = True

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(self.db_path)

    def search(self, *, cities: tuple[str, ...], tags: tuple[str, ...]) -> list[DataRecord]:
        city_set = {city.lower() for city in cities}
        tag_set = {tag.lower() for tag in tags}
        return [
            record
            for record in self._all_records
            if record.is_structured
            and (not city_set or record.city.lower() in city_set)
            and (not tag_set or tag_set.intersection(record.tags))
        ]

    def by_id(self, record_id: str) -> DataRecord:
        try:
            return self._records_by_id[record_id]
        except KeyError as exc:
            raise KeyError(record_id) from exc

    def get_schedule_record(self, content: str) -> DataRecord | None:
        for record in self._all_records:
            if record.content == content:
                return record
        return None

    def preference_names(self) -> tuple[str, ...]:
        with self._connect() as con:
            rows = con.execute("select preference_name_en from preference_master").fetchall()
        return tuple(row["preference_name_en"] for row in rows)

    def travel_time_minutes(self, origin_area_id: str, destination_area_id: str) -> int | None:
        if not origin_area_id or not destination_area_id or origin_area_id == destination_area_id:
            return 15
        with self._connect() as con:
            row = con.execute(
                """
                select estimated_time_min, estimated_time_max
                from travel_time_matrix
                where origin_entity_type = 'area'
                  and destination_entity_type = 'area'
                  and origin_entity_id = ?
                  and destination_entity_id = ?
                order by estimated_time_max
                limit 1
                """,
                (origin_area_id, destination_area_id),
            ).fetchone()
        if row is None:
            return None
        return int(((row["estimated_time_min"] or 0) + (row["estimated_time_max"] or 0)) / 2)

    @cached_property
    def _all_records(self) -> tuple[DataRecord, ...]:
        with self._connect() as con:
            return (
                *self._load_attractions(con),
                *self._load_restaurants(con),
                *self._load_markets(con),
                *self._load_activities(con),
                *self._load_cost_items(con),
            )

    @cached_property
    def _records_by_id(self) -> dict[str, DataRecord]:
        return {record.record_id: record for record in self._all_records}

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _load_attractions(self, con: sqlite3.Connection) -> Iterable[DataRecord]:
        rows = con.execute("select * from attraction_master").fetchall()
        for row in rows:
            tags = self._tags(
                row["travel_style_tags"],
                row["attraction_type"],
                self._preference_tags(con, "attraction_preference_map", "attraction_id", row["attraction_id"]),
            )
            yield DataRecord(
                record_id=row["attraction_id"],
                category="attraction",
                content=self._display_name(row["attraction_name_zh"], row["attraction_name_en"]),
                source_name=row["data_source_name"],
                url=row["source_url"],
                updated_at=row["last_checked_date"],
                is_structured=True,
                city=self._city_from_city_id(con, row["city_id"]),
                area_id=row["area_id"],
                cost_thb=self._attraction_cost(con, row["attraction_id"]),
                cost_note=self._attraction_cost_note(con, row["attraction_id"]),
                duration_min=self._duration(con, "attraction", row["attraction_id"], default_min=90),
                tags=tags,
            )

    def _load_restaurants(self, con: sqlite3.Connection) -> Iterable[DataRecord]:
        rows = con.execute("select * from restaurant_master").fetchall()
        for row in rows:
            tags = self._tags(
                row["travel_style_tags"],
                row["food_category"],
                row["dining_situation_tags"],
                self._preference_tags(con, "restaurant_preference_map", "restaurant_id", row["restaurant_id"]),
            )
            yield DataRecord(
                record_id=row["restaurant_id"],
                category="food",
                content=self._display_name(row["restaurant_name_zh"], row["restaurant_name_en"]),
                source_name=row["data_source_name"],
                url=row["source_url"],
                updated_at=row["last_checked_date"],
                is_structured=True,
                city=self._city_from_city_id(con, row["city_id"]),
                area_id=row["area_id"],
                cost_thb=self._price_midpoint(row["average_price_per_person"]),
                cost_note="平均餐費估算，實際金額會依點餐內容變動。",
                duration_min=self._duration(con, "restaurant", row["restaurant_id"], default_min=60),
                tags=tags,
            )

    def _load_markets(self, con: sqlite3.Connection) -> Iterable[DataRecord]:
        rows = con.execute("select * from market_master").fetchall()
        for row in rows:
            tags = self._tags(
                row["market_type"],
                row["opening_pattern"],
                row["best_time_slot"],
                row["main_features"],
                self._preference_tags(con, "market_preference_map", "market_id", row["market_id"]),
            )
            yield DataRecord(
                record_id=row["market_id"],
                category="market",
                content=self._display_name(row["market_name_zh"], row["market_name_en"]),
                source_name="DATA_FINAL market_master",
                url="",
                updated_at="",
                is_structured=True,
                city=self._city_from_area_id(con, row["area_id"]),
                area_id=row["area_id"],
                cost_thb=0,
                cost_note="市集/商圈本身通常不收門票，餐飲與購物另計。",
                duration_min=self._duration(con, "market", row["market_id"], default_min=90),
                tags=tags,
            )

    def _load_activities(self, con: sqlite3.Connection) -> Iterable[DataRecord]:
        rows = con.execute("select * from activity_master").fetchall()
        for row in rows:
            tags = self._tags(
                row["activity_type"],
                row["short_description"],
                self._preference_tags(con, "activity_preference_map", "activity_id", row["activity_id"]),
            )
            yield DataRecord(
                record_id=row["activity_id"],
                category="activity",
                content=self._display_name(row["activity_name_zh"], row["activity_name_en"]),
                source_name="DATA_FINAL activity_master",
                url=row["source_url"],
                updated_at="",
                is_structured=True,
                city=self._city_from_area_id(con, row["area_id"]),
                area_id=row["area_id"],
                cost_thb=0,
                cost_note="活動費用目前未在 cost_item_master 建立明確對應，需依平台或現場價格確認。",
                duration_min=int(((row["duration_min"] or 60) + (row["duration_max"] or row["duration_min"] or 60)) / 2),
                tags=tags,
            )

    def _load_cost_items(self, con: sqlite3.Connection) -> Iterable[DataRecord]:
        rows = con.execute("select * from cost_item_master").fetchall()
        for row in rows:
            yield DataRecord(
                record_id=row["cost_item_id"],
                category="cost",
                content=self._display_name(row["item_name_zh"], row["item_name_en"]),
                source_name=row["data_source_name"],
                url=row["source_url"],
                updated_at=row["last_checked_date"],
                is_structured=True,
                city=self._city_from_city_id(con, row["city_id"]),
                area_id=row["area_id"] or "",
                cost_thb=float(row["typical_price"] or row["min_price"] or 0),
                cost_note=row["cost_estimation_note"] or "",
                duration_min=30,
                tags=self._tags(row["cost_category"], row["cost_subcategory"], row["budget_level"]),
            )

    def _city_from_city_id(self, con: sqlite3.Connection, city_id: str | None) -> str:
        if not city_id:
            return ""
        row = con.execute("select city_name_en from city_master where city_id = ?", (city_id,)).fetchone()
        return row["city_name_en"] if row else city_id

    def _city_from_area_id(self, con: sqlite3.Connection, area_id: str | None) -> str:
        if not area_id:
            return ""
        row = con.execute("select city_name_en from area_master where area_id = ?", (area_id,)).fetchone()
        return row["city_name_en"] if row else area_id

    def _attraction_cost(self, con: sqlite3.Connection, attraction_id: str) -> float:
        row = con.execute(
            """
            select typical_price, min_price
            from cost_item_master
            where related_attraction_id = ?
            order by typical_price desc
            limit 1
            """,
            (attraction_id,),
        ).fetchone()
        if row is None:
            return 0
        return float(row["typical_price"] or row["min_price"] or 0)

    def _attraction_cost_note(self, con: sqlite3.Connection, attraction_id: str) -> str:
        row = con.execute(
            """
            select cost_estimation_note
            from cost_item_master
            where related_attraction_id = ?
            order by typical_price desc
            limit 1
            """,
            (attraction_id,),
        ).fetchone()
        if row and row["cost_estimation_note"]:
            return row["cost_estimation_note"]
        if attraction_id == "A002":
            return "可能已包含在大皇宮票券內，請以官方票券資訊為準。"
        return "資料庫尚無獨立票價，需人工確認是否免費、套票包含或另行購票。"

    def _duration(self, con: sqlite3.Connection, entity_type: str, entity_id: str, *, default_min: int) -> int:
        row = con.execute(
            """
            select min_duration_min, max_duration_min
            from visit_duration_reference
            where entity_type = ? and entity_id = ?
            limit 1
            """,
            (entity_type, entity_id),
        ).fetchone()
        if row is None:
            return default_min
        return int(((row["min_duration_min"] or default_min) + (row["max_duration_min"] or default_min)) / 2)

    def _preference_tags(
        self,
        con: sqlite3.Connection,
        map_table: str,
        entity_column: str,
        entity_id: str,
    ) -> tuple[str, ...]:
        rows = con.execute(
            f"""
            select p.preference_name_en, p.preference_name_zh
            from {map_table} m
            join preference_master p on p.preference_id = m.preference_id
            where m.{entity_column} = ?
            """,
            (entity_id,),
        ).fetchall()
        return self._tags(*[value for row in rows for value in (row["preference_name_en"], row["preference_name_zh"])])

    @staticmethod
    def _display_name(name_zh: str | None, name_en: str | None) -> str:
        if name_zh and name_en and name_zh != name_en:
            return f"{name_zh} / {name_en}"
        return name_zh or name_en or ""

    @staticmethod
    def _price_midpoint(value: Any) -> float:
        numbers = [float(number) for number in re.findall(r"\d+(?:\.\d+)?", str(value or ""))]
        if not numbers:
            return 0
        return sum(numbers[:2]) / min(len(numbers), 2)

    @classmethod
    def _tags(cls, *values: Any) -> tuple[str, ...]:
        tags: set[str] = set()
        for value in values:
            if value is None:
                continue
            if isinstance(value, (tuple, list, set)):
                tags.update(cls._tags(*value))
                continue
            for part in re.split(r"[;,/、，\s]+", str(value)):
                cleaned = part.strip().lower()
                if cleaned:
                    tags.add(cleaned)
        return tuple(sorted(tags))
