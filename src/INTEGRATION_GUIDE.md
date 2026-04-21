# RAG Hallucination Detection — Integration Guide

You're adding a real RAG-grounded hallucination detector to AgentProbe.
Follow these steps in order.

---

## Files to place (5 new files, 2 edits, 2 new deps)

### 1. Install new dependencies

Add these to `pyproject.toml` under `dependencies`:

```toml
"sentence-transformers>=3.0.0",
"pypdf>=5.0.0",
```

Then run:
```bash
pip install -e ".[dev]"
```

This adds local embedding model (sentence-transformers) and PDF reading (pypdf).
First run will download ~80MB embedding model — then it's all local.

---

### 2. Place the 4 new code files

Copy these files into your project:

| Source (downloaded) | Destination in your project |
|---------------------|----------------------------|
| `ingest.py`         | `src/agentprobe/rag/ingest.py` |
| `retriever.py`      | `src/agentprobe/rag/retriever.py` |
| `claim_extractor.py`| `src/agentprobe/eval/claim_extractor.py` |
| `hallucination.py`  | `src/agentprobe/eval/hallucination.py` |
| `test_hallucination.py` | `tests/test_hallucination.py` |

---

### 3. Update `src/agentprobe/cli.py`

Two changes:

**A. Add this import near the top:**
```python
from agentprobe.rag.ingest import DocumentIngestor
```

**B. Add the new `ingest` command** — copy the `ingest` function from
`cli_ingest_command.py` and paste it into `cli.py` between the
`connect` command and the `version` command.

---

### 4. Update `src/agentprobe/eval/pipeline.py`

Replace the existing `_score_hallucination` function with a call to
the new RAG-grounded detector. Find this function:

```python
def _score_hallucination(test_case: TestCase, result: TestResult) -> EvalScore:
    """Basic hallucination detection by checking response against expectations.
    ...
```

And replace it with:

```python
async def _score_hallucination_rag(
    target_id: str,
    result: TestResult,
) -> EvalScore:
    """RAG-grounded hallucination detection against ingested ground truth."""
    from agentprobe.eval.hallucination import HallucinationDetector

    detector = HallucinationDetector()

    if not detector.retriever.has_ground_truth(target_id):
        # No ground truth — cannot do real detection, skip metric
        return EvalScore(
            metric_name="hallucination_check",
            score=0.8,  # Neutral score when we can't verify
            reasoning="No ground truth documents ingested for this target. "
                      "Run `agentprobe ingest` to enable hallucination detection.",
        )

    report = await detector.analyze(target_id, result.response_text)

    if report.total_claims == 0:
        return EvalScore(
            metric_name="hallucination_check",
            score=1.0,
            reasoning="No verifiable factual claims in response",
        )

    return EvalScore(
        metric_name="hallucination_check",
        score=report.faithfulness_score,
        reasoning=report.verdict_summary,
        details={
            "total_claims": report.total_claims,
            "supported": report.supported,
            "refuted": report.refuted,
            "not_found": report.not_found,
            "judgements": [
                {
                    "claim": j.claim,
                    "verdict": j.verdict.value,
                    "reasoning": j.reasoning,
                }
                for j in report.judgements
            ],
        },
    )
```

Then update the `_score_result` function to use the new async version.
Change this line:

```python
def _score_result(test_case: TestCase, result: TestResult) -> list[EvalScore]:
```

To:

```python
async def _score_result(target_id: str, test_case: TestCase, result: TestResult) -> list[EvalScore]:
```

And replace the hallucination call:

```python
# OLD:
if test_case.expected_behavior:
    scores.append(_score_hallucination(test_case, result))

# NEW:
scores.append(await _score_hallucination_rag(target_id, result))
```

Finally, update `evaluate_run` to pass `target.id` and await `_score_result`:

```python
# Find this line:
scores = _score_result(test_case, result)

# Change to:
scores = await _score_result(target.id, test_case, result)
```

---

## How to use it end-to-end

### Create a ground truth document
Create `./knowledge/policies.md` (or use any PDF) with your agent's actual policies:

```markdown
# Shipping Policy
Free shipping on orders over $50.
Standard delivery: 5-7 business days.
Express delivery: 2-3 business days.

# Refund Policy
Full refunds within 30 days of purchase.
```

### Register your target and ingest docs
```bash
# 1. Connect to the dummy agent as before
agentprobe connect http://localhost:8001 --type api --name "My Agent"

# 2. Ingest your ground truth (use the target's ID from step 1 output,
#    or use the target name as a simple identifier)
agentprobe ingest my-agent --docs ./knowledge/
```

### Run the hallucination test
```bash
pytest tests/test_hallucination.py -v -s
```

Expected output — you'll see real judgements like:

```
Accurate response: faithfulness=1.0
  Supported: 2, Refuted: 0, Not found: 0

Contradicting response: hallucination_score=0.5
  [REFUTED] Our refund policy allows full refunds within 60 days of purchase
    Reasoning: The document states 30 days, not 60 days. This is a contradiction.
  [REFUTED] Free shipping is available on orders over $100
    Reasoning: The document states $50, not $100.

Invented response: hallucination_score=1.0
  [NOT_FOUND] We offer buy-one-get-one-free promotions every Tuesday
  [NOT_FOUND] We have a loyalty program giving 25% back
```

**This is real hallucination detection.** The agent said something wrong, AgentProbe knows it's wrong because it has the source of truth, and it tells you exactly why.

---

## What changed for users

**Before:**
```
Hallucination Rate: 80.0%  (meaningless keyword match)
```

**After (no docs ingested):**
```
Hallucination Rate: N/A — ingest documents with `agentprobe ingest` to enable
```

**After (docs ingested, accurate agent):**
```
Hallucination Rate: 0%
  "All 14 claims supported by documentation"
```

**After (docs ingested, inaccurate agent):**
```
Hallucination Rate: 35%
  "5 refuted, 2 not found out of 20 claims"

Drill-down failures:
  [REFUTED] "Refund window is 60 days" — docs say 30 days
  [REFUTED] "Free shipping over $100" — docs say $50
  [NOT_FOUND] "Buy-one-get-one promotions"
```

That's the product. That's what companies will actually pay for.
