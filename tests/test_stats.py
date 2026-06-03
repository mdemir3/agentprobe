"""Unit tests for eval/stats confidence intervals."""

from __future__ import annotations

import math
import statistics

import pytest
from scipy import stats as scipy_stats

from agentprobe.eval.stats import confidence_interval, wilson_interval


def test_t_ci_constant_values_zero_width():
    ci = confidence_interval([0.5, 0.5, 0.5])
    assert ci["mean"] == pytest.approx(0.5)
    assert ci["std"] == pytest.approx(0.0)
    assert ci["ci_low"] == pytest.approx(0.5)
    assert ci["ci_high"] == pytest.approx(0.5)
    assert ci["ci_high"] - ci["ci_low"] == pytest.approx(0.0)
    assert ci["method"] == "t"
    assert ci["n"] == 3


def test_t_ci_alternating_values_predictable_width():
    values = [0.0, 1.0] * 5
    n = len(values)
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    tcrit = scipy_stats.t.ppf(0.975, df=n - 1)
    margin = tcrit * std / math.sqrt(n)

    ci = confidence_interval(values)
    assert ci["mean"] == pytest.approx(mean)
    assert ci["std"] == pytest.approx(std)
    assert ci["ci_low"] == pytest.approx(mean - margin, rel=1e-4)
    assert ci["ci_high"] == pytest.approx(mean + margin, rel=1e-4)
    assert ci["ci_high"] - ci["ci_low"] == pytest.approx(2 * margin, rel=1e-4)
    assert ci["method"] == "t"
    assert ci["n"] == 10


def test_wilson_90_of_100():
    ci = wilson_interval(90, 100)
    assert ci["mean"] == pytest.approx(0.9)
    assert ci["ci_low"] == pytest.approx(0.824, abs=0.01)
    assert ci["ci_high"] == pytest.approx(0.945, abs=0.01)
    assert ci["method"] == "wilson"
    assert ci["n"] == 100


@pytest.mark.parametrize(
    "values",
    [
        [0.0, 1.0] * 5,
        [0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
        [0.1, 0.9, 0.2, 0.8, 0.15],
        [1.0, 1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
    ],
)
def test_t_ci_score_bounds_within_unit_interval(values):
    ci = confidence_interval(values)
    assert 0.0 <= ci["ci_low"] <= 1.0
    assert 0.0 <= ci["ci_high"] <= 1.0
    assert ci["ci_low"] <= ci["ci_high"]
