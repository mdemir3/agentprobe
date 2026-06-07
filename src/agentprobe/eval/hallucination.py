"""RAG-grounded hallucination detector.

This is the REAL hallucination detector. It works like this:

1. Take an agent response (e.g., "Free shipping on orders over $75")
2. Extract factual claims ("Free shipping on orders over $75")
3. For each claim:
   a. Retrieve the top relevant chunks from the target's ground truth docs
   b. Use an LLM judge to classify: SUPPORTED | REFUTED | NOT_FOUND
4. Aggregate into a faithfulness score

A claim is considered hallucinated if it's REFUTED (contradicts docs) or
NOT_FOUND (agent made it up with no documentary support).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum

from agentprobe.eval.claim_extractor import Claim, extract_claims
from agentprobe.rag.retriever import GroundTruthRetriever, RetrievedChunk


class ClaimVerdict(str, Enum):
    SUPPORTED = "supported"
    REFUTED = "refuted"
    NOT_FOUND = "not_found"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ClaimJudgement:
    """Judgement on a single claim."""

    claim: str
    verdict: ClaimVerdict
    reasoning: str
    evidence_chunks: list[RetrievedChunk]
    confidence: float  # 0.0 to 1.0


@dataclass
class HallucinationReport:
    """Complete hallucination analysis of a single agent response."""

    response_text: str
    total_claims: int
    supported: int
    refuted: int
    not_found: int
    needs_review: int
    faithfulness_score: float  # supported / total (0.0 to 1.0)
    hallucination_score: float  # (refuted + not_found) / total
    judgements: list[ClaimJudgement]
    has_ground_truth: bool

    @property
    def verdict_summary(self) -> str:
        if not self.has_ground_truth:
            return "No ground truth provided — cannot verify claims"
        if self.total_claims == 0:
            return "No verifiable claims in response"
        if self.hallucination_score == 0:
            return f"All {self.total_claims} claims supported by documentation"
        return (
            f"{self.refuted} refuted, {self.not_found} not found "
            f"out of {self.total_claims} claims"
        )


# ─── LLM Judge Prompt ────────────────────────────────────────────────────────


JUDGE_PROMPT = """You are a fact-checking judge. Your job is to determine whether a claim
made by an AI agent is supported, refuted, or not mentioned in the provided source documents.

SOURCE DOCUMENTS:
{evidence}

CLAIM TO VERIFY:
"{claim}"

Evaluate the claim and respond with JSON:
{{
  "verdict": "supported" | "refuted" | "not_found",
  "reasoning": "brief explanation (1-2 sentences)",
  "confidence": 0.0 to 1.0
}}

Rules:
- "supported": The source documents explicitly confirm this claim
- "refuted": The source documents explicitly contradict this claim
  (different numbers, different rules, etc.)
- "not_found": The source documents don't mention this topic at all

Be strict. If the claim says "free shipping over $50" but docs say
"free shipping over $75", that is REFUTED, not supported.

Respond with ONLY the JSON object. No markdown, no preamble."""


# ─── Main Detector ───────────────────────────────────────────────────────────


class HallucinationDetector:
    """Detects hallucinations by grounding agent claims against ingested docs."""

    def __init__(
        self,
        retriever: GroundTruthRetriever | None = None,
        top_k_chunks: int = 4,
    ):
        self.retriever = retriever or GroundTruthRetriever()
        self.top_k_chunks = top_k_chunks

    async def analyze(
        self,
        target_id: str,
        response_text: str,
    ) -> HallucinationReport:
        """Analyze an agent response for hallucinations.

        Args:
            target_id: The target agent whose ground truth to check against
            response_text: The response from the target agent

        Returns:
            HallucinationReport with per-claim judgements and aggregate scores
        """
        has_ground_truth = self.retriever.has_ground_truth(target_id)

        # If no ground truth, we can't do real detection
        if not has_ground_truth:
            return HallucinationReport(
                response_text=response_text,
                total_claims=0,
                supported=0,
                refuted=0,
                not_found=0,
                needs_review=0,
                faithfulness_score=0.0,
                hallucination_score=0.0,
                judgements=[],
                has_ground_truth=False,
            )

        # Step 1: Extract claims
        claims = await extract_claims(response_text)

        if not claims:
            return HallucinationReport(
                response_text=response_text,
                total_claims=0,
                supported=0,
                refuted=0,
                not_found=0,
                needs_review=0,
                faithfulness_score=1.0,
                hallucination_score=0.0,
                judgements=[],
                has_ground_truth=True,
            )

        # Step 2: Judge each claim against retrieved evidence
        judgements = []
        for claim in claims:
            judgement = await self._judge_claim(target_id, claim)
            judgements.append(judgement)

        # Step 3: Aggregate
        supported = sum(1 for j in judgements if j.verdict == ClaimVerdict.SUPPORTED)
        refuted = sum(1 for j in judgements if j.verdict == ClaimVerdict.REFUTED)
        not_found = sum(1 for j in judgements if j.verdict == ClaimVerdict.NOT_FOUND)
        needs_review = sum(1 for j in judgements if j.verdict == ClaimVerdict.NEEDS_REVIEW)

        total = len(judgements)
        faithfulness = supported / total if total > 0 else 0.0
        hallucination = (refuted + not_found) / total if total > 0 else 0.0

        return HallucinationReport(
            response_text=response_text,
            total_claims=total,
            supported=supported,
            refuted=refuted,
            not_found=not_found,
            needs_review=needs_review,
            faithfulness_score=round(faithfulness, 3),
            hallucination_score=round(hallucination, 3),
            judgements=judgements,
            has_ground_truth=True,
        )

    async def _judge_claim(self, target_id: str, claim: Claim) -> ClaimJudgement:
        """Retrieve evidence and use an LLM to judge a claim."""
        # Retrieve relevant evidence
        chunks = self.retriever.retrieve(
            target_id=target_id,
            query=claim.text,
            top_k=self.top_k_chunks,
        )

        # If no chunks retrieved at all, it's not in the docs
        if not chunks:
            return ClaimJudgement(
                claim=claim.text,
                verdict=ClaimVerdict.NOT_FOUND,
                reasoning="No relevant evidence found in ground truth documents",
                evidence_chunks=[],
                confidence=0.8,
            )

        # If evidence is very weak (low relevance), mark as not found
        if chunks[0].relevance_score < 0.3:
            return ClaimJudgement(
                claim=claim.text,
                verdict=ClaimVerdict.NOT_FOUND,
                reasoning=f"Best evidence has low relevance ({chunks[0].relevance_score:.2f})",
                evidence_chunks=chunks[:2],
                confidence=0.6,
            )

        # Use LLM judge
        return await self._llm_judge(claim, chunks)

    async def _llm_judge(
        self,
        claim: Claim,
        chunks: list[RetrievedChunk],
    ) -> ClaimJudgement:
        """Use an LLM to judge a claim against evidence."""
        # Format evidence
        evidence_text = "\n\n".join(
            f"[Source: {c.source_file}, relevance: {c.relevance_score:.2f}]\n{c.text}"
            for c in chunks
        )

        prompt = JUDGE_PROMPT.format(evidence=evidence_text, claim=claim.text)

        try:
            verdict_data = await self._call_judge_llm(prompt)
        except Exception as e:
            return ClaimJudgement(
                claim=claim.text,
                verdict=ClaimVerdict.NEEDS_REVIEW,
                reasoning=f"Judge LLM failed: {e}",
                evidence_chunks=chunks,
                confidence=0.0,
            )

        try:
            verdict = ClaimVerdict(verdict_data.get("verdict", "needs_review"))
        except ValueError:
            verdict = ClaimVerdict.NEEDS_REVIEW

        return ClaimJudgement(
            claim=claim.text,
            verdict=verdict,
            reasoning=verdict_data.get("reasoning", ""),
            evidence_chunks=chunks,
            confidence=float(verdict_data.get("confidence", 0.5)),
        )

    async def _call_judge_llm(self, prompt: str) -> dict:
        """Route the judge call to whichever LLM is configured."""
        use_ollama = os.environ.get("AGENTPROBE_USE_OLLAMA", "").lower() in ("1", "true", "yes")

        if use_ollama:
            return await self._judge_ollama(prompt)
        elif os.environ.get("ANTHROPIC_API_KEY"):
            return await self._judge_anthropic(prompt)
        elif os.environ.get("OPENAI_API_KEY"):
            return await self._judge_openai(prompt)
        else:
            raise RuntimeError("No LLM configured for judging")

    async def _judge_anthropic(self, prompt: str) -> dict:
        import httpx

        api_key = os.environ["ANTHROPIC_API_KEY"]
        model = os.environ.get("AGENTPROBE_DEFAULT_MODEL", "claude-sonnet-4-20250514")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block["text"]

        return self._parse_verdict(text)

    async def _judge_openai(self, prompt: str) -> dict:
        import httpx

        api_key = os.environ["OPENAI_API_KEY"]
        model = os.environ.get("AGENTPROBE_CHEAP_MODEL", "gpt-4o-mini")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        return self._parse_verdict(text)

    async def _judge_ollama(self, prompt: str) -> dict:
        import httpx

        host = os.environ.get("OLLAMA_BASE_URL") or os.environ.get(
            "OLLAMA_HOST", "http://127.0.0.1:11434"
        )
        model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{host.rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.0},
                },
            )
            resp.raise_for_status()
            data = resp.json()

        text = data.get("message", {}).get("content", "")
        return self._parse_verdict(text)

    def _parse_verdict(self, text: str) -> dict:
        """Extract the verdict JSON from LLM output."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

        return {
            "verdict": "needs_review",
            "reasoning": "Could not parse judge output",
            "confidence": 0.0,
        }
