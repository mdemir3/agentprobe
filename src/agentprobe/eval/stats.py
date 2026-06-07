"""Statistical helpers for multi-run probe evaluation."""

from __future__ import annotations

import math
import statistics
from typing import Any

from scipy import stats as scipy_stats

_SCORE_BOUNDS = (0.0, 1.0)


def _clip_score_bounds(ci_low: float, ci_high: float) -> tuple[float, float]:
    lo, hi = _SCORE_BOUNDS
    return max(lo, min(hi, ci_low)), max(lo, min(hi, ci_high))


def wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Wilson score interval for a binomial proportion (successes / trials)."""
    if trials <= 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "method": "wilson",
            "n": 0,
        }

    p_hat = successes / trials
    ci_low, ci_high = _wilson_bounds(p_hat, trials, confidence)

    return {
        "mean": round(p_hat, 4),
        "std": 0.0,
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "method": "wilson",
        "n": trials,
    }


def _wilson_bounds(p_hat: float, n: int, confidence: float) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    if n == 1:
        return _clip_score_bounds(p_hat, p_hat)

    z = scipy_stats.norm.ppf(0.5 + confidence / 2.0)
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2.0 * n)) / denom
    margin = (z / denom) * math.sqrt((p_hat * (1.0 - p_hat) / n) + z2 / (4.0 * n * n))
    return _clip_score_bounds(center - margin, center + margin)


def proportion_confidence_interval(
    per_case_values: list[float],
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Wilson CI using the mean of per-case rates as p_hat and n = number of cases."""
    n = len(per_case_values)
    if n == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "method": "wilson",
            "n": 0,
        }

    mean = statistics.mean(per_case_values)
    std = statistics.stdev(per_case_values) if n > 1 else 0.0
    ci_low, ci_high = _wilson_bounds(mean, n, confidence)

    return {
        "mean": round(mean, 4),
        "std": std,
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "method": "wilson",
        "n": n,
    }


def confidence_interval(
    values: list[float],
    confidence: float = 0.95,
    *,
    clip_bounds: tuple[float, float] | None = _SCORE_BOUNDS,
) -> dict[str, Any]:
    """Mean, sample std, and two-sided t-based CI (df = n - 1)."""
    n = len(values)
    if n == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "ci_low": 0.0,
            "ci_high": 0.0,
            "method": "t",
            "n": 0,
        }

    mean = statistics.mean(values)
    if n == 1:
        ci_low, ci_high = mean, mean
        if clip_bounds is not None:
            ci_low, ci_high = _clip_score_bounds(ci_low, ci_high)
        return {
            "mean": round(mean, 4),
            "std": 0.0,
            "ci_low": round(ci_low, 6),
            "ci_high": round(ci_high, 6),
            "method": "t",
            "n": 1,
        }

    std = statistics.stdev(values)
    if std == 0.0:
        ci_low, ci_high = mean, mean
    else:
        alpha = 1.0 - confidence
        tcrit = scipy_stats.t.ppf(1.0 - alpha / 2.0, df=n - 1)
        margin = tcrit * std / math.sqrt(n)
        ci_low, ci_high = mean - margin, mean + margin

    if clip_bounds is not None:
        ci_low, ci_high = _clip_score_bounds(ci_low, ci_high)

    return {
        "mean": round(mean, 4),
        "std": std,
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "method": "t",
        "n": n,
    }


def mean_and_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.stdev(values)
