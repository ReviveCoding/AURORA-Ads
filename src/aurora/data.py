"""Source-specific streaming container/schema gates. No cross-source identity joins."""
from __future__ import annotations

import gzip
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as csv

R1_COLUMNS = ("timestamp", "uid", "campaign", "conversion", "conversion_timestamp", "conversion_id", "attribution", "click", "click_pos", "click_nb", "cost", "cpo", "time_since_last_click", *(f"cat{i}" for i in range(1, 10)))
R2_COLUMNS = (*(f"f{i}" for i in range(12)), "treatment", "conversion", "visit", "exposure")
R3_COLUMNS = ("Sale", "SalesAmountInEuro", "time_delay_for_conversion", "click_timestamp", "nb_clicks_1week", "product_price", "product_age_group", "device_type", "audience_id", "product_gender", "product_brand", *(f"product_category{i}" for i in range(1, 8)), "product_country", "product_id", "product_title", "partner_id", "user_id")


@dataclass(frozen=True)
class SourceSchema:
    source_id: str
    evidence_domain: str
    separator: str
    required: tuple[str, ...]
    binary: tuple[str, ...]
    numeric: tuple[str, ...]
    features: tuple[str, ...]


SCHEMAS = {
    "criteo_attribution": SourceSchema("criteo_attribution", "R1", "\t", R1_COLUMNS, ("conversion", "attribution", "click"), ("timestamp", "conversion_timestamp", "cost", "cpo", "time_since_last_click"), ("campaign", *(f"cat{i}" for i in range(1, 10)))),
    "criteo_uplift": SourceSchema("criteo_uplift", "R2", ",", R2_COLUMNS, ("treatment", "conversion", "visit", "exposure"), tuple(f"f{i}" for i in range(12)), tuple(f"f{i}" for i in range(12))),
    "obd_men": SourceSchema("obd_men", "R4", ",", ("timestamp", "item_id", "position", "click", "propensity_score"), ("click",), ("item_id", "position", "propensity_score"), ()),
    "criteo_search": SourceSchema("criteo_search", "R3", "\t", R3_COLUMNS, ("Sale",), ("SalesAmountInEuro", "time_delay_for_conversion", "click_timestamp", "product_price"), ("device_type", "audience_id", "product_brand", *(f"product_category{i}" for i in range(1, 8)), "product_country", "product_id", "product_title", "partner_id")),
}


class BoundedReader(io.RawIOBase):
    """Counts decompressed bytes; gzip wrapper verifies CRC when EOF is reached."""

    def __init__(self, stream: BinaryIO, limit: int):
        super().__init__()
        self.stream = stream
        self.limit = limit
        self.count = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer) -> int:
        data = self.stream.read(min(len(buffer), self.limit - self.count + 1))
        self.count += len(data)
        if self.count > self.limit:
            raise ValueError("Decompressed byte ceiling exceeded")
        buffer[:len(data)] = data
        return len(data)


def open_batches(path: Path, schema: SourceSchema, *, decompressed_limit: int = 8 * 1024**3):
    """Caller must consume to EOF before claiming CONTAINER_VALID."""
    with path.open("rb") as raw:
        with (gzip.GzipFile(fileobj=raw) if path.name.endswith(".gz") else io.BufferedReader(raw)) as source:
            bounded = BoundedReader(source, min(decompressed_limit, max(path.stat().st_size * 100, 1024**2)))
            reader = csv.open_csv(io.BufferedReader(bounded), read_options=csv.ReadOptions(block_size=1024**2, use_threads=False), parse_options=csv.ParseOptions(delimiter=schema.separator), convert_options=csv.ConvertOptions(column_types={key: pa.string() for key in (*schema.binary, *schema.numeric)}))
            if not set(schema.required).issubset(reader.schema.names):
                raise ValueError("Required source schema columns absent")
            for batch in reader:
                table = pa.Table.from_batches([batch])
                for key in (*schema.binary, *schema.numeric):
                    try:
                        values = pc.cast(table[key], pa.float64())
                    except pa.ArrowInvalid:
                        # Only malformed batches take this bounded fallback. Bad
                        # numerics become null and are quarantined by valid_rows.
                        converted = []
                        for value in table[key].to_pylist():
                            try:
                                converted.append(float(value) if value is not None else None)
                            except (ValueError, TypeError):
                                converted.append(None)
                        values = pa.array(converted, type=pa.float64())
                    table = table.set_column(table.schema.get_field_index(key), key, values)
                yield table, bounded


def valid_rows(table: pa.Table, schema: SourceSchema) -> tuple[pa.Array | pa.ChunkedArray, dict[str, int]]:
    valid = pa.array([True] * len(table))
    reasons = {}
    for key in (*schema.binary, *schema.numeric):
        column = table[key]
        good = pc.fill_null(pc.is_finite(column), False)
        if key in schema.binary:
            good = pc.and_(good, pc.is_in(column, value_set=pa.array([0., 1.])))
        if key == "propensity_score":
            good = pc.and_(good, pc.and_(pc.greater(column, 0), pc.less_equal(column, 1)))
        if key == "timestamp" and schema.evidence_domain == "R1":
            good = pc.and_(good, pc.greater_equal(column, 0))
        if key == "click_timestamp":
            good = pc.and_(good, pc.greater(column, 0))
        bad_count = len(table) - pc.sum(pc.cast(good, pa.int64())).as_py()
        if bad_count:
            reasons[key] = bad_count
        valid = pc.and_(valid, good)
    return valid, reasons


def eligible_features(source_id: str, columns: tuple[str, ...]) -> None:
    if not set(columns).issubset(SCHEMAS[source_id].features):
        raise ValueError("Outcome/post-assignment/unqualified feature is forbidden")


@dataclass(frozen=True)
class ClockRecord:
    origin_time: float
    information_time: float
    received_at: float | None
    horizon_seconds: float = 7 * 86400

    def eligible(self, snapshot: float) -> bool:
        if not all(math.isfinite(value) for value in (self.origin_time, self.information_time, snapshot, self.horizon_seconds)) or self.horizon_seconds <= 0:
            raise ValueError("Invalid clock")
        return self.origin_time <= snapshot and self.information_time <= snapshot

    def observed(self, snapshot: float) -> bool:
        if self.received_at is not None and (not math.isfinite(self.received_at) or self.received_at < self.origin_time):
            raise ValueError("Receipt precedes origin or is nonfinite")
        return self.received_at is not None and self.received_at <= snapshot

    def mature(self, snapshot: float) -> bool:
        return self.origin_time + self.horizon_seconds <= snapshot


def r3_partition(origin_seconds: float) -> str:
    day = origin_seconds / 86400
    for name, lower, upper in (("M41", 0, 41), ("C54", 41, 47), ("selection", 54, 60), ("final", 70, 82)):
        if lower <= day < upper:
            return name
    return "excluded"
