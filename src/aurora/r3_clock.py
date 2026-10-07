"""Explicit duration/schema-supported R3 clock qualification, not epoch guessing."""
from __future__ import annotations

import math


def infer_clock_scale(native_span: float, documented_days: float = 90.) -> dict:
    if not math.isfinite(native_span) or native_span <= 0 or documented_days != 90.:
        raise ValueError("Finite native span and publisher90-day duration required")
    # The publisher duration describes a sampled traffic window, not exact
    # endpoint equality. Up to two calendar boundaries allow inclusive-day
    # conventions; this is a declared admission assumption, not label fitting.
    candidates = {"seconds": 1., "milliseconds": .001, "microseconds": .000001,
                  "minutes": 60., "hours": 3600., "days": 86400.}
    matches = [(unit, scale) for unit, scale in candidates.items()
               if abs(native_span * scale / 86400 - documented_days) <= 2.]
    if len(matches) != 1:
        raise ValueError("Publisher duration/schema do not uniquely identify clock scale")
    unit, scale = matches[0]
    return {"native_unit": unit, "seconds_per_native_unit": scale,
            "documented_sample_days": documented_days, "observed_span_days": native_span * scale / 86400,
            "basis": "INFERRED_FROM_DOCUMENTED_DURATION_AND_SCHEMA; not explicitly publisher-declared",
            "duration_tolerance_days": 2., "calendar_epoch_asserted": False}


def check_delay_schema(*, min_positive_delay: float, max_positive_delay: float,
                       clock_scale: float, bad_nonconversion_delays: int) -> None:
    if not all(math.isfinite(value) for value in (min_positive_delay, max_positive_delay, clock_scale)):
        raise ValueError("No valid observed conversion-delay schema")
    if clock_scale <= 0 or min_positive_delay < 0 or max_positive_delay * clock_scale > 30 * 86400 or bad_nonconversion_delays:
        raise ValueError("Conversion-delay semantics inconsistent with publisher30-day window")
