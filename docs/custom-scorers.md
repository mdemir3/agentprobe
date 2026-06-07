# Writing Custom Eval Scorers

AgentProbe evaluates each test result with a set of **scorers**, each producing
an `EvalScore`. This guide explains the built-in scorers and how to add your own.

## The `EvalScore` model

Every scorer returns an `EvalScore` (`src/agentprobe/probe/models.py`):

```python
class EvalScore(BaseModel):
    metric_name: str
    score: float        # 0.0 – 1.0
    reasoning: str = ""
    details: dict = {}
```

A test case's `overall_score` is the mean of its scorers' `score` values; a case
passes when that mean is ≥ 0.7.

## Built-in scorers

These live in `src/agentprobe/eval/pipeline.py`:

| Function | `metric_name` | What it measures |
|----------|---------------|------------------|
| `_score_tool_accuracy` | `tool_accuracy` | Precision/recall of tool selection vs. `tools_expected` |
| `_score_response_quality` | `response_quality` | Penalizes empty/very short/refusal responses |
| `_score_safety` | `safety` | Flags prompt-injection success and PII leakage (adversarial/safety cases) |
| `_score_hallucination_rag` | `hallucination_check` | RAG-grounded faithfulness vs. ingested ground truth |

They are dispatched in `_score_result(...)`, which decides which scorers apply to
a given `TestCase` (e.g. safety only runs for `ADVERSARIAL`/`SAFETY` categories).

## Adding a scorer

1. Write a function that takes the test case/result and returns an `EvalScore`:

```python
def _score_response_length(test_case: TestCase, result: TestResult) -> EvalScore:
    n = len(result.response_text.split())
    score = 1.0 if 10 <= n <= 300 else 0.5
    return EvalScore(
        metric_name="response_length",
        score=score,
        reasoning=f"{n} words",
        details={"word_count": n},
    )
```

2. Register it in `_score_result(...)`:

```python
scores.append(_score_response_length(test_case, result))
```

3. (Optional) If it represents a **rate/proportion** you want aggregated with a
   confidence interval, accumulate a per-case value and add it to the `ci`
   dict in `evaluate_run(...)` using `proportion_confidence_interval(...)`
   (Wilson). Continuous metrics use `confidence_interval(...)` (t-distribution).
   See `src/agentprobe/eval/stats.py`.

## How aggregation works

For multi-run probes, scores are averaged **per test case first**, then a
confidence interval is computed **across per-case means** (so `n` is the number
of test cases, not the number of invocations). Rate metrics use a Wilson score
interval; continuous metrics use a t-distribution with `df = n - 1`. Score CIs
are clipped to `[0, 1]`.
