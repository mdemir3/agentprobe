"""Claim extractor — Uses an LLM to decompose agent responses into factual claims.

Before we can check for hallucinations, we need to identify the specific
factual claims the agent made. An agent response like "We offer free shipping
on orders over $50 and delivery takes 5-7 business days" contains two claims
that should be verified independently.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class Claim:
    """A single factual assertion extracted from an agent response."""

    text: str
    category: str  # factual | policy | numeric | reference | opinion


CLAIM_EXTRACTION_PROMPT = """You extract factual claims from AI assistant responses.

A factual claim is a statement that could be verified as true or false against documentation.
Examples of claims:
- "Free shipping on orders over $50"
- "Our refund window is 30 days"
- "Processing takes 2-3 business days"
- "We accept Visa, Mastercard, and AMEX"

NOT claims (don't extract these):
- Questions ("How can I help you?")
- Greetings ("Hello!")
- Opinions ("I think that's great")
- Meta-statements ("I'll check that for you")

Given the following agent response, extract every distinct factual claim.

Response to analyze:
{response}

Output a JSON array of claims. Each claim object has:
- text: the claim stated as a complete sentence
- category: one of "factual" (general facts), "policy" (rules/procedures),
  "numeric" (numbers/prices/durations), "reference" (names/identifiers)

Respond with ONLY the JSON array. No markdown, no preamble.

Example output:
[
  {{"text": "Free shipping is available on orders over $50", "category": "policy"}},
  {{"text": "Standard delivery takes 5 to 7 business days", "category": "numeric"}}
]

If there are no verifiable factual claims, return an empty array: []"""


async def extract_claims(response_text: str) -> list[Claim]:
    """Extract factual claims from an agent response.

    Tries LLM-based extraction first (Ollama > Anthropic > OpenAI),
    falls back to heuristic extraction if no LLM is available.
    """
    if not response_text or len(response_text.strip()) < 10:
        return []

    use_ollama = os.environ.get("AGENTPROBE_USE_OLLAMA", "").lower() in ("1", "true", "yes")

    try:
        claims: list[Claim] = []
        if use_ollama:
            claims = await _extract_with_ollama(response_text)
        elif os.environ.get("ANTHROPIC_API_KEY"):
            claims = await _extract_with_anthropic(response_text)
        elif os.environ.get("OPENAI_API_KEY"):
            claims = await _extract_with_openai(response_text)
        if claims:
            return claims
    except Exception as e:
        print(f"Claim extraction fell back to heuristic: {e}")

    return _extract_heuristic(response_text)


async def _extract_with_anthropic(response_text: str) -> list[Claim]:
    import httpx

    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("AGENTPROBE_DEFAULT_MODEL", "claude-sonnet-4-20250514")

    prompt = CLAIM_EXTRACTION_PROMPT.format(response=response_text)

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
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()

    text = ""
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block["text"]

    return _parse_claims(text)


async def _extract_with_openai(response_text: str) -> list[Claim]:
    import httpx

    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("AGENTPROBE_CHEAP_MODEL", "gpt-4o-mini")

    prompt = CLAIM_EXTRACTION_PROMPT.format(response=response_text)

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
                "max_tokens": 2000,
                "temperature": 0.0,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"]
    return _parse_claims(text)


async def _extract_with_ollama(response_text: str) -> list[Claim]:
    import httpx

    host = os.environ.get("OLLAMA_BASE_URL") or os.environ.get(
        "OLLAMA_HOST", "http://127.0.0.1:11434"
    )
    model = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")

    prompt = CLAIM_EXTRACTION_PROMPT.format(response=response_text)

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
    return _parse_claims(text)


def _parse_claims(text: str) -> list[Claim]:
    """Parse LLM output into Claim objects. Handles various formats."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Handle case where LLM wrapped array in an object
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end])
            except json.JSONDecodeError:
                return []
        else:
            return []

    # If the LLM returned a dict with "claims" key, unwrap it
    if isinstance(parsed, dict):
        parsed = parsed.get("claims", parsed.get("items", []))

    if not isinstance(parsed, list):
        return []

    claims = []
    for item in parsed:
        if isinstance(item, dict) and "text" in item:
            claims.append(
                Claim(
                    text=item["text"],
                    category=item.get("category", "factual"),
                )
            )
        elif isinstance(item, str):
            claims.append(Claim(text=item, category="factual"))

    return claims


def _extract_heuristic(response_text: str) -> list[Claim]:
    """Fallback heuristic extraction — splits on sentences, filters to likely claims."""
    import re

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", response_text.strip())

    claims = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue

        # Skip likely non-claims
        lower = sentence.lower()
        skip_patterns = [
            "how can i help",
            "let me know",
            "please let me",
            "feel free",
            "i'm here to",
            "is there anything",
            "i understand",
            "i apologize",
        ]
        if any(p in lower for p in skip_patterns):
            continue

        # Skip pure questions
        if sentence.endswith("?"):
            continue

        claims.append(Claim(text=sentence.rstrip("."), category="factual"))

    return claims
