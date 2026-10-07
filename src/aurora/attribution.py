"""Descriptive credited-touch allocation, never incremental-effect truth."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


# Internal offline analyst query, never available as arbitrary agent SQL.
# Caller binds half-life and supplies only source-qualified ``credited`` rows.
ALLOCATION_SQL = """
WITH ranges AS (
 SELECT *, MIN(timestamp) OVER(PARTITION BY conversion_id) AS first_origin,
 MAX(timestamp) OVER(PARTITION BY conversion_id) AS last_origin FROM credited
), raw AS (
 SELECT *, CASE WHEN timestamp=first_origin THEN 1.0 ELSE 0.0 END AS first_raw,
 CASE WHEN timestamp=last_origin THEN 1.0 ELSE 0.0 END AS last_raw,
 EXP(LN(2.0)*(timestamp-last_origin)/?) AS decay_raw FROM ranges
), weighted AS (
 SELECT *, first_raw/SUM(first_raw) OVER(PARTITION BY conversion_id) AS first_weight,
 last_raw/SUM(last_raw) OVER(PARTITION BY conversion_id) AS last_weight,
 decay_raw/SUM(decay_raw) OVER(PARTITION BY conversion_id) AS decay_weight FROM raw
)
SELECT campaign,COUNT(*) AS credited_rows,SUM(first_weight) AS first_touch,
SUM(last_weight) AS last_touch,SUM(decay_weight) AS time_decay
FROM weighted GROUP BY campaign ORDER BY campaign
"""


@dataclass(frozen=True)
class CreditedTouch:
    conversion_id: int
    user_id: str
    campaign: str
    origin: float
    occurrence: float


def path_weights(touches: Sequence[CreditedTouch], *, half_life_native: float) -> dict[str, list[float]]:
    """Allocate one released conversion ID among its credited source rows.

    Ties share first/last credit. Rows are not invented unique impressions;
    repeated native timestamps are retained. No time-unit/calendar inference.
    """
    if not touches or not math.isfinite(half_life_native) or half_life_native <= 0:
        raise ValueError("Nonempty admitted path and positive native half-life required")
    if len({touch.conversion_id for touch in touches}) != 1 or touches[0].conversion_id < 0 or len({touch.user_id for touch in touches}) != 1 or len({touch.occurrence for touch in touches}) != 1:
        raise ValueError("One compatible nonnegative released conversion ID/user/occurrence required")
    if any(not all(math.isfinite(value) for value in (touch.origin, touch.occurrence)) or touch.origin > touch.occurrence for touch in touches):
        raise ValueError("Finite occurrence after every credited origin required")
    low, high = min(touch.origin for touch in touches), max(touch.origin for touch in touches)
    first_count = sum(touch.origin == low for touch in touches)
    last_count = sum(touch.origin == high for touch in touches)
    # Subtract high before exponentiation: stable ratios even for old paths.
    raw = [math.exp(math.log(2.) * (touch.origin - high) / half_life_native) for touch in touches]
    total = math.fsum(raw)
    return {"first_touch": [float(touch.origin == low) / first_count for touch in touches], "last_touch": [float(touch.origin == high) / last_count for touch in touches], "time_decay": [value / total for value in raw]}
