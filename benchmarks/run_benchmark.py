#!/usr/bin/env python3
"""Run AgentProbe benchmarks across agents × RAG corpora.

Usage (from repository root):
    python benchmarks/run_benchmark.py
    python benchmarks/run_benchmark.py --max-cases 12 --skip-ingest  # faster re-run

Outputs:
    benchmarks/results/summary.json
    benchmarks/results/<agent>__<corpus>.json
    benchmarks/results/charts/*.png
    benchmarks/results/REPORT.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Repository root on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.agents.registry import AGENTS, AGENT_BY_ID  # noqa: E402
from benchmarks.lib.heuristic_judge import load_corpus_text, score_response  # noqa: E402
from agentprobe.connectors.api_connector import APIConnector  # noqa: E402
from agentprobe.eval.pipeline import evaluate_run  # noqa: E402
from agentprobe.probe.planner import generate_test_plan  # noqa: E402
from agentprobe.probe.runner import execute_test_run  # noqa: E402
from agentprobe.rag.ingest import DocumentIngestor  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"
CHROMA_DIR = RESULTS_DIR / "chromadb"
DATASETS_DIR = Path(__file__).parent / "datasets"

CORPORA = [
    ("technical_docs", DATASETS_DIR / "technical_docs"),
    ("policy_legal", DATASETS_DIR / "policy_legal"),
    ("product_faq", DATASETS_DIR / "product_faq"),
]


def _run_agent_server(agent_id: str) -> None:
    """Subprocess entry: start one benchmark agent."""
    os.environ.setdefault("BENCHMARK_CORPUS", "technical_docs")
    os.environ.setdefault(
        "BENCHMARK_CORPUS_ROOT",
        str(DATASETS_DIR / os.environ["BENCHMARK_CORPUS"]),
    )
    import uvicorn

    from benchmarks.agents.registry import load_agent_app

    spec = AGENT_BY_ID[agent_id]
    app = load_agent_app(agent_id)
    uvicorn.run(app, host="127.0.0.1", port=spec.port, log_level="error")


def _start_agent(agent_id: str, corpus_id: str) -> multiprocessing.Process:
    os.environ["BENCHMARK_CORPUS"] = corpus_id
    os.environ["BENCHMARK_CORPUS_ROOT"] = str(DATASETS_DIR / corpus_id)
    proc = multiprocessing.Process(
        target=_run_agent_server,
        args=(agent_id,),
        daemon=True,
    )
    proc.start()
    time.sleep(1.5)
    return proc


def _stop_agent(proc: multiprocessing.Process) -> None:
    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)


def _target_id(agent_id: str, corpus_id: str) -> str:
    return f"{agent_id}__{corpus_id}"


async def _run_single(
    agent_id: str,
    corpus_id: str,
    corpus_dir: Path,
    max_cases: int,
    skip_ingest: bool,
) -> dict:
    spec = AGENT_BY_ID[agent_id]
    url = f"http://127.0.0.1:{spec.port}"
    tid = _target_id(agent_id, corpus_id)
    corpus_text = load_corpus_text(corpus_dir)

    os.environ["AGENTPROBE_CHROMA_DATA"] = str(CHROMA_DIR)
    os.environ["AGENTPROBE_CHROMA_USE_HTTP"] = "false"

    if not skip_ingest:
        ingestor = DocumentIngestor(chroma_path=str(CHROMA_DIR))
        ingestor.ingest_folder(
            target_id=tid,
            folder_path=str(corpus_dir),
            patterns=["*.md"],
        )

    async with APIConnector(url=url, name=spec.profile.display_name) as connector:
        discovered = await connector.discover()
        profile = discovered.model_copy(update={"id": tid})

        plan = await generate_test_plan(
            target=profile,
            name=f"Benchmark {agent_id} / {corpus_id}",
            max_cases=max_cases,
        )

        run = await execute_test_run(plan=plan, target=profile, max_concurrent=4)
        report = await evaluate_run(run=run, plan=plan, target=profile)

    # Heuristic hallucination (works offline; complements AgentProbe RAG judge)
    heuristic_scores = []
    for result in run.results:
        if result.response_text:
            heuristic_scores.append(
                score_response(corpus_id, corpus_text, result.response_text)
            )

    avg_heuristic_hallucination = 0.0
    if heuristic_scores:
        avg_heuristic_hallucination = sum(
            s["hallucination_rate"] for s in heuristic_scores
        ) / len(heuristic_scores)

    latencies = [r.latency_ms for r in run.results if r.latency_ms > 0]

    return {
        "agent_id": agent_id,
        "agent_name": spec.profile.display_name,
        "framework": spec.profile.framework,
        "corpus_id": corpus_id,
        "target_id": tid,
        "url": url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plan_cases": plan.total_cases,
        "report": report.model_dump(mode="json"),
        "heuristic_hallucination_rate": round(avg_heuristic_hallucination, 3),
        "latencies_ms": latencies,
        "profile": {
            "hallucination_bias": spec.profile.hallucination_bias,
            "tool_miss_rate": spec.profile.tool_miss_rate,
        },
    }


async def run_all(max_cases: int, skip_ingest: bool) -> list[dict]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # Rule-based planner only (no API keys required for benchmark harness)
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AGENTPROBE_USE_OLLAMA", "AGENTPROBE_USE_MCP_BRIDGE"):
        os.environ.pop(key, None)

    results: list[dict] = []
    total = len(AGENTS) * len(CORPORA)
    n = 0

    for agent_spec in AGENTS:
        for corpus_id, corpus_dir in CORPORA:
            n += 1
            print(f"[{n}/{total}] {agent_spec.agent_id} × {corpus_id} …", flush=True)

            proc = _start_agent(agent_spec.agent_id, corpus_id)
            try:
                cell = await _run_single(
                    agent_spec.agent_id,
                    corpus_id,
                    corpus_dir,
                    max_cases=max_cases,
                    skip_ingest=skip_ingest,
                )
                results.append(cell)

                out_path = RESULTS_DIR / f"{agent_spec.agent_id}__{corpus_id}.json"
                out_path.write_text(json.dumps(cell, indent=2), encoding="utf-8")
                print(
                    f"    → score={cell['report']['overall_score']:.1%} "
                    f"hallucination={cell['heuristic_hallucination_rate']:.1%} "
                    f"tool_acc={cell['report']['tool_accuracy']:.1%}",
                    flush=True,
                )
            finally:
                _stop_agent(proc)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agents": [a.agent_id for a in AGENTS],
        "corpora": [c[0] for c in CORPORA],
        "max_cases": max_cases,
        "cells": results,
    }
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentProbe benchmark harness")
    parser.add_argument("--max-cases", type=int, default=12, help="Test cases per plan")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Reuse existing Chroma collections",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip matplotlib chart generation",
    )
    args = parser.parse_args()

    print("AgentProbe Benchmark Run")
    print("=" * 50)
    results = asyncio.run(run_all(args.max_cases, args.skip_ingest))

    if not args.no_charts:
        from benchmarks.visualize import generate_charts, write_report

        chart_paths = generate_charts(results, RESULTS_DIR / "charts")
        write_report(results, chart_paths, RESULTS_DIR / "REPORT.md")
        print(f"\nReport: {RESULTS_DIR / 'REPORT.md'}")
        print(f"Charts: {RESULTS_DIR / 'charts'}/")
    else:
        print(f"\nSummary: {RESULTS_DIR / 'summary.json'}")


if __name__ == "__main__":
    main()
