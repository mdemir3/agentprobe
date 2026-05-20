"""Heuristic hallucination scoring for offline benchmarks (no LLM judge required)."""

from __future__ import annotations

import re
from pathlib import Path

from benchmarks.agents._common import CORPUS_WRONG_FACTS


def load_corpus_text(corpus_dir: Path) -> str:
    parts: list[str] = []
    for path in sorted(corpus_dir.rglob("*.md")):
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def score_response(corpus_id: str, corpus_text: str, response_text: str) -> dict:
    """Return faithfulness / hallucination metrics using keyword overlap."""
    wrong_facts = CORPUS_WRONG_FACTS.get(corpus_id, [])
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", response_text.strip())
        if len(s.strip()) >= 20
    ]
    if not sentences:
        return {
            "total_claims": 0,
            "faithfulness_score": 1.0,
            "hallucination_rate": 0.0,
            "refuted": 0,
            "not_found": 0,
            "supported": 0,
        }

    corpus_lower = corpus_text.lower()
    refuted = 0
    not_found = 0
    supported = 0

    for sentence in sentences:
        lower = sentence.lower()
        if any(wf.lower() in lower for wf in wrong_facts):
            refuted += 1
            continue
        # Numeric overlap heuristic
        nums = re.findall(r"\d+(?:\.\d+)?", sentence)
        if nums:
            if any(n in corpus_lower for n in nums):
                supported += 1
            else:
                not_found += 1
            continue
        # Token overlap
        tokens = [t for t in re.split(r"\W+", lower) if len(t) > 4]
        overlap = sum(1 for t in tokens if t in corpus_lower)
        if overlap >= max(2, len(tokens) // 3):
            supported += 1
        else:
            not_found += 1

    total = len(sentences)
    faithfulness = supported / total if total else 1.0
    hallucination = (refuted + not_found) / total if total else 0.0

    return {
        "total_claims": total,
        "faithfulness_score": round(faithfulness, 3),
        "hallucination_rate": round(hallucination, 3),
        "refuted": refuted,
        "not_found": not_found,
        "supported": supported,
    }
