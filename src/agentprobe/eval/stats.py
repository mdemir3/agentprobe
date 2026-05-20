"""Statistical helpers for multi-run probe evaluation."""

from __future__ import annotations

import statistics
from typing import Any

# Two-tailed t critical values for 95% CI (df = n-1), stdlib-only fallback
_T_CRIT_95: dict[int, float] = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    25: 2.060,
    30: 2.042,
}


def _t_critical(df: int, confidence_level: float) -> float:
    if df <= 0:
        return 0.0
    if confidence_level >= 0.99:
        # Conservative wide interval for small samples
        table = {1: 63.657, 2: 9.925, 3: 5.841, 5: 4.032, 10: 3.169, 30: 2.750}
    else:
        table = _T_CRIT_95
    if df in table:
        return table[df]
    if df < 30:
        # Linear interpolate between nearest tabulated dfs
        keys = sorted(k for k in table if k <= df)
        if not keys:
            return table[min(table)]
        lo = keys[-1]
        hi = min((k for k in table if k > df), default=30)
        if lo == hi:
            return table[lo]
        frac = (df - lo) / (hi - lo)
        return table[lo] + frac * (table[hi] - table[lo])
    return 1.96 if confidence_level >= 0.95 else 1.645


def confidence_interval(
    values: list[float],
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Mean, sample std, and two-sided confidence interval."""
    n = len(values)
    if n == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "confidence_level": confidence_level,
            "n": 0,
        }
    mean = statistics.mean(values)
    if n == 1:
        return {
            "mean": round(mean, 4),
            "std": 0.0,
            "ci_low": round(mean, 4),
            "ci_high": round(mean, 4),
            "confidence_level": confidence_level,
            "n": 1,
        }
    std = statistics.stdev(values)
    tcrit = _t_critical(n - 1, confidence_level)
    margin = tcrit * std / (n**0.5)
    return {
        "mean": round(mean, 4),
        "std": round(std, 4),
        "ci_low": round(mean - margin, 4),
        "ci_high": round(mean + margin, 4),
        "confidence_level": confidence_level,
        "n": n,
    }


def mean_and_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)
