"""Generate matplotlib charts and REPORT.md for benchmark results."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
def _require_matplotlib():
    try:
        import matplotlib  # noqa: F401

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: F401

        return plt
    except ImportError as e:
        raise SystemExit(
            "matplotlib is required for charts. Install with: pip install matplotlib"
        ) from e


def _agent_aggregate(results: list[dict]) -> dict[str, dict[str, float]]:
    """Average metrics per agent across corpora."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in results:
        buckets[row["agent_id"]].append(row)

    agg: dict[str, dict[str, float]] = {}
    for agent_id, rows in buckets.items():
        agg[agent_id] = {
            "hallucination_rate": statistics.mean(
                r.get("heuristic_hallucination_rate", r["report"]["hallucination_rate"])
                for r in rows
            ),
            "tool_accuracy": statistics.mean(r["report"]["tool_accuracy"] for r in rows),
            "overall_score": statistics.mean(r["report"]["overall_score"] for r in rows),
            "avg_latency_ms": statistics.mean(r["report"]["avg_latency_ms"] for r in rows),
            "display_name": rows[0]["agent_name"],
        }
    return agg


def generate_charts(results: list[dict], charts_dir: Path) -> dict[str, Path]:
    """Create PNG charts; return map of chart key → path."""
    plt = _require_matplotlib()
    charts_dir.mkdir(parents=True, exist_ok=True)
    agg = _agent_aggregate(results)
    agents = list(agg.keys())
    labels = [agg[a]["display_name"] for a in agents]
    paths: dict[str, Path] = {}

    # 1. Hallucination rate by agent
    fig, ax = plt.subplots(figsize=(10, 5))
    values = [agg[a]["hallucination_rate"] * 100 for a in agents]
    colors = plt.cm.Reds([v / max(values + [1]) for v in values])
    bars = ax.bar(labels, values, color=colors, edgecolor="#333", linewidth=0.6)
    ax.set_ylabel("Hallucination rate (%)")
    ax.set_title("Hallucination Rate by Agent (avg across corpora)")
    ax.set_ylim(0, max(values) * 1.25 + 5)
    plt.xticks(rotation=20, ha="right")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    p = charts_dir / "hallucination_rate_by_agent.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths["hallucination"] = p

    # 2. Tool accuracy by agent
    fig, ax = plt.subplots(figsize=(10, 5))
    values = [agg[a]["tool_accuracy"] * 100 for a in agents]
    colors = plt.cm.Greens([v / 100 for v in values])
    bars = ax.bar(labels, values, color=colors, edgecolor="#333", linewidth=0.6)
    ax.set_ylabel("Tool accuracy (%)")
    ax.set_title("Tool Call Accuracy by Agent (avg across corpora)")
    ax.set_ylim(0, 105)
    plt.xticks(rotation=20, ha="right")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    fig.tight_layout()
    p = charts_dir / "tool_accuracy_by_agent.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths["tool_accuracy"] = p

    # 3. Latency distribution (all probe latencies)
    fig, ax = plt.subplots(figsize=(10, 5))
    all_latencies: list[float] = []
    agent_latency_series: dict[str, list[float]] = defaultdict(list)
    for row in results:
        for ms in row.get("latencies_ms", []):
            all_latencies.append(ms)
            agent_latency_series[row["agent_id"]].append(ms)

    if all_latencies:
        ax.hist(
            all_latencies,
            bins=min(30, max(10, len(all_latencies) // 5)),
            color="#4F46E5",
            alpha=0.75,
            edgecolor="white",
        )
        ax.set_xlabel("Latency (ms)")
        ax.set_ylabel("Probe count")
        ax.set_title("Latency Distribution (all agents & corpora)")
        ax.axvline(
            statistics.median(all_latencies),
            color="#DC2626",
            linestyle="--",
            label=f"median {statistics.median(all_latencies):.0f} ms",
        )
        ax.legend()
    fig.tight_layout()
    p = charts_dir / "latency_distribution.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths["latency"] = p

    # 4. Heatmap: agent × corpus overall score
    corpora = sorted({r["corpus_id"] for r in results})
    matrix = []
    for agent_id in agents:
        row_scores = []
        for corpus in corpora:
            match = next(
                (r for r in results if r["agent_id"] == agent_id and r["corpus_id"] == corpus),
                None,
            )
            row_scores.append(match["report"]["overall_score"] * 100 if match else 0)
        matrix.append(row_scores)

    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(corpora)))
    ax.set_xticklabels(corpora)
    ax.set_yticks(range(len(agents)))
    ax.set_yticklabels([agg[a]["display_name"] for a in agents])
    ax.set_title("Overall Quality Score (%) — Agent × Corpus")
    for i in range(len(agents)):
        for j in range(len(corpora)):
            ax.text(j, i, f"{matrix[i][j]:.0f}", ha="center", va="center", color="black", fontsize=9)
    fig.colorbar(im, ax=ax, label="Score %")
    fig.tight_layout()
    p = charts_dir / "score_heatmap.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    paths["heatmap"] = p

    return paths


def write_report(
    results: list[dict],
    chart_paths: dict[str, Path],
    report_path: Path,
) -> None:
    """Write LinkedIn-ready REPORT.md with tables and chart embeds."""
    agg = _agent_aggregate(results)
    agents_sorted = sorted(
        agg.keys(),
        key=lambda a: agg[a]["overall_score"],
        reverse=True,
    )

    lines = [
        "# AgentProbe Benchmark Report",
        "",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
        f"**Matrix:** {len(agg)} agents × {len({r['corpus_id'] for r in results})} RAG corpora  ",
        f"**Runs:** {len(results)} probe executions  ",
        "",
        "> Autonomous QA for AI agents — comparable scores across LangChain, CrewAI, OpenAI Assistants, AutoGen, and MCP.",
        "",
        "## Executive summary",
        "",
    ]

    best = agents_sorted[0]
    worst = agents_sorted[-1]
    lines.extend(
        [
            f"- **Highest overall score:** {agg[best]['display_name']} ({agg[best]['overall_score']:.1%})",
            f"- **Lowest overall score:** {agg[worst]['display_name']} ({agg[worst]['overall_score']:.1%})",
            f"- **Lowest hallucination rate:** "
            f"{agg[min(agg, key=lambda a: agg[a]['hallucination_rate'])]['display_name']} "
            f"({min(agg[a]['hallucination_rate'] for a in agg):.1%} avg)",
            "",
            "## Charts",
            "",
            "### Hallucination rate by agent",
            "",
            f"![Hallucination rate](charts/{chart_paths['hallucination'].name})",
            "",
            "### Tool accuracy by agent",
            "",
            f"![Tool accuracy](charts/{chart_paths['tool_accuracy'].name})",
            "",
            "### Latency distribution",
            "",
            f"![Latency distribution](charts/{chart_paths['latency'].name})",
            "",
            "### Quality score heatmap (agent × corpus)",
            "",
            f"![Score heatmap](charts/{chart_paths['heatmap'].name})",
            "",
            "## Aggregate results (avg across corpora)",
            "",
            "| Agent | Framework | Overall | Hallucination | Tool accuracy | Avg latency |",
            "|-------|-----------|---------|---------------|---------------|-------------|",
        ]
    )

    def framework_for(aid: str) -> str:
        return next(r for r in results if r["agent_id"] == aid)["framework"]

    for agent_id in agents_sorted:
        m = agg[agent_id]
        lines.append(
            f"| {m['display_name']} | {framework_for(agent_id)} | "
            f"{m['overall_score']:.1%} | {m['hallucination_rate']:.1%} | "
            f"{m['tool_accuracy']:.1%} | {m['avg_latency_ms']:.0f} ms |"
        )

    lines.extend(
        [
            "",
            "## Full matrix (overall score)",
            "",
            "| Agent | " + " | ".join(sorted({r["corpus_id"] for r in results})) + " |",
            "|-------|" + "|".join(["------"] * len({r["corpus_id"] for r in results})) + "|",
        ]
    )

    corpora = sorted({r["corpus_id"] for r in results})
    for agent_id in agents_sorted:
        cells = []
        for corpus in corpora:
            match = next(
                (r for r in results if r["agent_id"] == agent_id and r["corpus_id"] == corpus),
                None,
            )
            cells.append(f"{match['report']['overall_score']:.1%}" if match else "—")
        lines.append(f"| {agg[agent_id]['display_name']} | " + " | ".join(cells) + " |")

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "See [README.md](../README.md) for corpus descriptions, agent wrappers, and reproduction steps.",
            "",
            "---",
            "",
            "*Built with [AgentProbe](https://github.com/mdemir3/agentprobe) — FastAPI · LangGraph · ChromaDB · DeepEval*",
        ]
    )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    """Regenerate charts + REPORT.md from existing summary.json."""
    results_dir = Path(__file__).parent / "results"
    summary_path = results_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"No results found at {summary_path}. Run run_benchmark.py first.")

    data = json.loads(summary_path.read_text(encoding="utf-8"))
    results: list[dict] = data["cells"]
    charts_dir = results_dir / "charts"
    chart_paths = generate_charts(results, charts_dir)
    write_report(results, chart_paths, results_dir / "REPORT.md")
    print(f"Wrote {results_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
