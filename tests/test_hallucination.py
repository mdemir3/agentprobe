"""End-to-end test for RAG-grounded hallucination detection.

This test:
1. Creates a ground truth document (shipping & refund policies)
2. Ingests it into ChromaDB
3. Tests an agent response that MATCHES the docs (should score high faithfulness)
4. Tests an agent response that CONTRADICTS the docs (should flag hallucinations)
5. Tests an agent response that INVENTS claims not in docs (should flag not_found)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from agentprobe.eval.hallucination import HallucinationDetector
from agentprobe.rag.ingest import DocumentIngestor
from agentprobe.rag.retriever import GroundTruthRetriever


def _llm_configured_for_judging() -> bool:
    if (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return True
    if (os.environ.get("OPENAI_API_KEY") or "").strip():
        return True
    return os.environ.get("AGENTPROBE_USE_OLLAMA", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


GROUND_TRUTH_DOC = """
# Customer Support Policies

## Refund Policy
Customers can request a full refund within 30 days of purchase.
After 30 days, a 50% refund is available for up to 90 days.
No refunds are issued after 90 days.

## Shipping Policy
Standard shipping takes 5-7 business days and costs $5.99.
Express shipping takes 2-3 business days and costs $14.99.
Free standard shipping is available on orders over $50.
International shipping takes 10-14 business days.

## Warranty
All electronics come with a 1-year manufacturer warranty.
Extended warranty can be purchased within the first 30 days.
"""


@pytest.fixture(scope="module")
def test_target_id():
    return "test_target_hallucination"


@pytest.fixture(scope="module")
def chroma_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture(scope="module")
def ingested_target(test_target_id, chroma_path):
    """Ingest the ground truth document."""
    # Write doc to temp file
    with tempfile.TemporaryDirectory() as docs_dir:
        doc_path = Path(docs_dir) / "policies.md"
        doc_path.write_text(GROUND_TRUTH_DOC)

        ingestor = DocumentIngestor(chroma_path=chroma_path)
        result = ingestor.ingest_folder(
            target_id=test_target_id,
            folder_path=docs_dir,
            patterns=["*.md"],
        )

        assert result.files_processed == 1
        assert result.chunks_created > 0

    yield test_target_id


@pytest.mark.asyncio
async def test_accurate_response_high_faithfulness(ingested_target, chroma_path):
    """An accurate response should have high faithfulness score."""
    if not _llm_configured_for_judging():
        pytest.skip("No LLM configured for judging")

    retriever = GroundTruthRetriever(chroma_path=chroma_path)
    detector = HallucinationDetector(retriever=retriever)

    accurate_response = (
        "Our refund policy allows full refunds within 30 days of purchase. "
        "Standard shipping takes 5 to 7 business days."
    )

    report = await detector.analyze(ingested_target, accurate_response)

    assert report.has_ground_truth
    assert report.total_claims >= 1
    assert report.faithfulness_score >= 0.7
    print(f"\nAccurate response: faithfulness={report.faithfulness_score}")
    print(f"  Supported: {report.supported}, Refuted: {report.refuted}, Not found: {report.not_found}")


@pytest.mark.asyncio
async def test_contradicting_response_flagged_as_refuted(ingested_target, chroma_path):
    """A response contradicting docs should be flagged as REFUTED."""
    if not _llm_configured_for_judging():
        pytest.skip("No LLM configured for judging")

    retriever = GroundTruthRetriever(chroma_path=chroma_path)
    detector = HallucinationDetector(retriever=retriever)

    # Wrong numbers — docs say 30 days, agent says 60 days
    contradicting_response = (
        "Our refund policy allows full refunds within 60 days of purchase. "
        "Free shipping is available on orders over $100."
    )

    report = await detector.analyze(ingested_target, contradicting_response)

    assert report.has_ground_truth
    assert report.refuted >= 1  # At least one claim should be refuted
    assert report.hallucination_score > 0

    print(f"\nContradicting response: hallucination_score={report.hallucination_score}")
    for j in report.judgements:
        print(f"  [{j.verdict.value.upper()}] {j.claim[:80]}")
        print(f"    Reasoning: {j.reasoning}")


@pytest.mark.asyncio
async def test_invented_claims_flagged_as_not_found(ingested_target, chroma_path):
    """Claims not in the docs should be flagged as NOT_FOUND."""
    if not _llm_configured_for_judging():
        pytest.skip("No LLM configured for judging")

    retriever = GroundTruthRetriever(chroma_path=chroma_path)
    detector = HallucinationDetector(retriever=retriever)

    # Completely invented — nothing about buy-one-get-one in the docs
    invented_response = (
        "We offer buy-one-get-one-free promotions every Tuesday. "
        "We also have a loyalty program that gives you 25% back on all purchases."
    )

    report = await detector.analyze(ingested_target, invented_response)

    assert report.has_ground_truth
    assert report.not_found >= 1

    print(f"\nInvented response: hallucination_score={report.hallucination_score}")
    for j in report.judgements:
        print(f"  [{j.verdict.value.upper()}] {j.claim[:80]}")


@pytest.mark.asyncio
async def test_no_ground_truth_graceful_fallback():
    """Without ingested docs, detector should return gracefully."""
    retriever = GroundTruthRetriever()
    detector = HallucinationDetector(retriever=retriever)

    report = await detector.analyze("nonexistent_target", "Some response")

    assert not report.has_ground_truth
    assert "No ground truth" in report.verdict_summary
