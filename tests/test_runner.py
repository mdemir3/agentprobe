"""Tests for probe runner behavior (temperature, multi-run variance)."""

from __future__ import annotations

import pytest

from agentprobe.connectors.ollama_connector import OllamaConnector
from agentprobe.probe.runner import resolve_temperature


def test_resolve_temperature_warns_and_bumps_zero(capsys):
    """runs > 1 with temperature=0 should warn and return 0.7."""
    resolved = resolve_temperature(runs=3, temperature=0.0)
    assert resolved == 0.7
    err = capsys.readouterr().err
    assert "temperature=0" in err
    assert "Setting temperature to 0.7" in err


def test_resolve_temperature_unchanged_when_positive():
    assert resolve_temperature(runs=3, temperature=0.5) == 0.5
    assert resolve_temperature(runs=1, temperature=0.0) == 0.0


def test_ollama_chat_options_include_temperature():
    connector = OllamaConnector("http://127.0.0.1:11434", temperature=0.7)
    opts = connector._chat_options(seed=42, temperature=0.7)
    assert opts["temperature"] == 0.7
    assert opts["seed"] == 42


@pytest.mark.asyncio
async def test_ollama_repetitions_differ_with_temperature():
    """Three reps at temperature=0.7 should not all be identical."""
    connector = OllamaConnector(
        "http://127.0.0.1:11434",
        model="",
        temperature=0.7,
    )
    try:
        await connector.connect()
    except ConnectionError:
        pytest.skip("Ollama not running at http://127.0.0.1:11434")

    prompt = (
        "Invent a unique fictional product name and one-sentence description. "
        "Do not repeat common examples."
    )
    responses: list[str] = []
    try:
        for seed in (101, 202, 303):
            result = await connector.invoke(prompt, seed=seed, temperature=0.7)
            assert not result.get("error"), result.get("error")
            text = (result.get("response_text") or "").strip()
            assert text, "Expected non-empty response from Ollama"
            responses.append(text)
    finally:
        await connector.disconnect()

    unique = len(set(responses))
    assert unique >= 2, (
        f"Expected at least 2 distinct responses with temperature=0.7, "
        f"got {unique}: {responses!r}"
    )
