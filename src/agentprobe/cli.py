"""AgentProbe CLI — Test AI agents from the command line."""

from __future__ import annotations

import asyncio
import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from agentprobe.connectors.api_connector import APIConnector
from agentprobe.connectors.mcp_connector import MCPConnector
from agentprobe.connectors.ollama_connector import OllamaConnector
from agentprobe.eval.pipeline import evaluate_run
from agentprobe.probe.models import ConnectorType, QualityReport, TargetProfile
from agentprobe.probe.planner import generate_test_plan
from agentprobe.probe.runner import execute_test_run

console = Console()


def _run_async(coro):
    """Run an async coroutine from sync CLI context."""
    return asyncio.run(coro)


@click.group()
@click.version_option(version="0.1.0", prog_name="AgentProbe")
def cli():
    """AgentProbe — The first AI agent that tests other AI agents.

    Discover, probe, and evaluate any LLM-powered agent automatically.
    """
    pass


@cli.command()
@click.argument("url")
@click.option(
    "--type",
    "connector_type",
    type=click.Choice(["mcp", "api"], case_sensitive=False),
    default="api",
    help="Connector type: mcp or api",
)
@click.option("--name", default="", help="Friendly name for this target agent")
@click.option("--auth-token", default="", help="Authorization bearer token")
@click.option("--chat-endpoint", default="/chat", help="Chat endpoint path (API only)")
@click.option("--tools-endpoint", default="/tools", help="Tools endpoint path (API only)")
@click.option("--output", "-o", default="", help="Save profile to JSON file")
def connect(
    url: str,
    connector_type: str,
    name: str,
    auth_token: str,
    chat_endpoint: str,
    tools_endpoint: str,
    output: str,
):
    """Connect to a target AI agent and discover its capabilities.

    Examples:

        agentprobe connect http://localhost:8001 --type api

        agentprobe connect http://localhost:9000/mcp --type mcp

        agentprobe connect http://localhost:8001 --name "My RAG Agent" -o profile.json
    """
    _run_async(
        _connect_async(
            url, connector_type, name, auth_token, chat_endpoint, tools_endpoint, output
        )
    )


async def _connect_async(
    url: str,
    connector_type: str,
    name: str,
    auth_token: str,
    chat_endpoint: str,
    tools_endpoint: str,
    output: str,
):
    console.print(f"\n[bold blue]AgentProbe[/] connecting to [cyan]{url}[/]...\n")

    connector = _create_connector(
        url, connector_type, name, auth_token, chat_endpoint, tools_endpoint
    )

    try:
        async with connector:
            profile = await connector.discover()
            _display_profile(profile)

            if output:
                with open(output, "w") as f:
                    json.dump(profile.model_dump(mode="json"), f, indent=2, default=str)
                console.print(f"\n[green]Profile saved to {output}[/]")

    except ConnectionError as e:
        console.print(f"\n[red bold]Connection failed:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red bold]Error:[/] {e}")
        sys.exit(1)


def _create_connector(
    url: str,
    connector_type: str,
    name: str,
    auth_token: str,
    chat_endpoint: str,
    tools_endpoint: str,
    model: str = "",
    temperature: float = 0.7,
):
    kind = connector_type.lower()
    if kind == "mcp":
        return MCPConnector(url=url, name=name, auth_token=auth_token)
    if kind in ("rest", "ollama"):
        return OllamaConnector(
            url=url,
            name=name,
            model=model or "llama3.1",
            temperature=temperature,
        )
    return APIConnector(
        url=url,
        name=name,
        auth_token=auth_token,
        chat_endpoint=chat_endpoint,
        tools_endpoint=tools_endpoint,
    )


def _display_profile(profile: TargetProfile):
    """Display the discovered target profile in a rich format."""

    # Header
    console.print(
        Panel(
            f"[bold]{profile.name}[/]\n"
            f"[dim]{profile.url}[/]\n"
            f"Type: [cyan]{profile.connector_type.value}[/]  |  "
            f"Tools: [green]{len(profile.tools)}[/]  |  "
            f"Resources: [yellow]{len(profile.resources)}[/]",
            title="[bold blue]Target Agent Profile[/]",
            border_style="blue",
        )
    )

    # Tools table
    if profile.tools:
        table = Table(
            title="Discovered Tools",
            show_header=True,
            header_style="bold cyan",
            border_style="dim",
        )
        table.add_column("Tool Name", style="bold")
        table.add_column("Description", max_width=50)
        table.add_column("Required Params", style="yellow")
        table.add_column("All Params", style="dim")

        for tool in profile.tools:
            required = ", ".join(tool.required_params) if tool.required_params else "—"
            all_params = ", ".join(tool.parameters.keys()) if tool.parameters else "—"
            table.add_row(tool.name, tool.description[:50], required, all_params)

        console.print(table)

    # Resources
    if profile.resources:
        tree = Tree("[bold yellow]Resources[/]")
        for res in profile.resources:
            tree.add(f"[cyan]{res.name}[/] — {res.description} ({res.uri})")
        console.print(tree)

    if not profile.tools and not profile.resources:
        console.print("[yellow]No tools or resources discovered.[/]")

    console.print(
        f"\n[bold green]Discovery complete.[/] "
        f"Found [cyan]{len(profile.tools)}[/] tools and "
        f"[cyan]{len(profile.resources)}[/] resources.\n"
    )


@cli.command()
@click.argument("url")
@click.option(
    "--type",
    "connector_type",
    type=click.Choice(["rest", "api", "mcp", "ollama"], case_sensitive=False),
    default="rest",
    help="Target type: rest/ollama (Ollama API), api (agent REST), mcp",
)
@click.option("--tests", default=20, show_default=True, help="Number of test cases to run")
@click.option(
    "--model",
    default="llama3.1",
    show_default=True,
    help="Ollama model name (rest/ollama only)",
)
@click.option("--name", default="", help="Friendly name for the target")
@click.option("--concurrency", default=3, show_default=True, help="Parallel test executions")
@click.option(
    "--runs",
    default=1,
    show_default=True,
    help="Execute each test case N times (seeds: base+0 … base+N-1)",
)
@click.option(
    "--seed",
    default=0,
    show_default=True,
    help="Base random seed passed to the target (e.g. Ollama options.seed)",
)
@click.option("-o", "--output", default="", help="Write full report JSON (incl. confidence_interval)")
@click.option(
    "--temperature",
    default=0.7,
    show_default=True,
    type=float,
    help="Ollama sampling temperature (use >0 with --runs >1 for variance)",
)
def probe(
    url: str,
    connector_type: str,
    tests: int,
    model: str,
    name: str,
    concurrency: int,
    runs: int,
    seed: int,
    output: str,
    temperature: float,
):
    """Probe a target end-to-end and print a quality report.

    Day-one local LLM (zero API cost):

        ollama run llama3.1

        agentprobe probe http://localhost:11434 --type rest --tests 50 --runs 3 --model llama3.1

    Tool/API agents:

        agentprobe probe http://localhost:8001 --type api --tests 20
    """
    _run_async(
        _probe_async(
            url,
            connector_type,
            tests,
            model,
            name,
            concurrency,
            runs,
            seed,
            output,
            temperature,
        )
    )


async def _probe_async(
    url: str,
    connector_type: str,
    tests: int,
    model: str,
    name: str,
    concurrency: int,
    runs: int,
    seed: int,
    output: str,
    temperature: float,
) -> None:
    import os

    normalized = connector_type.lower()
    is_ollama = normalized in ("rest", "ollama")

    if is_ollama:
        os.environ["AGENTPROBE_USE_OLLAMA"] = "true"
        os.environ["OLLAMA_BASE_URL"] = url.rstrip("/")
        os.environ["OLLAMA_MODEL"] = model
        os.environ["AGENTPROBE_USE_MCP_BRIDGE"] = "false"
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    runs = max(1, runs)
    display_name = name or (f"Ollama ({model})" if is_ollama else url)
    console.print(
        Panel(
            f"[bold]Target[/] {display_name}\n"
            f"[dim]{url}[/]  ·  type={connector_type}  ·  tests={tests}  ·  "
            f"runs={runs}  ·  seed={seed}  ·  temperature={temperature}",
            title="[bold blue]AgentProbe Probe[/]",
            border_style="blue",
        )
    )

    connector = _create_connector(
        url,
        connector_type,
        display_name,
        "",
        "/chat",
        "/tools",
        model=model if is_ollama else "",
        temperature=temperature if is_ollama else 0.7,
    )

    try:
        async with connector:
            console.print("[cyan]Discovering capabilities…[/]")
            profile = await connector.discover()
            if is_ollama:
                profile = profile.model_copy(
                    update={
                        "metadata": {
                            **profile.metadata,
                            "temperature": temperature,
                            "model": model,
                        }
                    }
                )

            console.print("[cyan]Generating test plan…[/]")
            plan = await generate_test_plan(
                target=profile,
                name=f"Probe — {display_name}",
                max_cases=tests,
            )
            if profile.connector_type == ConnectorType.OLLAMA:
                for tc in plan.test_cases:
                    tc.tools_expected = []
            console.print(f"  [green]{plan.total_cases}[/] test cases\n")

            total_invocations = plan.total_cases * runs
            console.print(
                f"[cyan]Running probes…[/] "
                f"({plan.total_cases} cases × {runs} runs = {total_invocations} invocations)"
            )
            run = await execute_test_run(
                plan=plan,
                target=profile,
                max_concurrent=concurrency,
                runs=runs,
                seed=seed,
                temperature=temperature,
            )

            console.print("[cyan]Evaluating results…[/]\n")
            report = await evaluate_run(
                run=run, plan=plan, target=profile, runs=runs, seed=seed
            )
            _display_quality_report(report)

            if output:
                with open(output, "w") as f:
                    json.dump(report.model_dump(mode="json"), f, indent=2, default=str)
                console.print(f"[green]Report JSON saved to {output}[/]\n")

    except ConnectionError as e:
        console.print(f"\n[red bold]Connection failed:[/] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red bold]Probe failed:[/] {e}")
        sys.exit(1)


def _display_quality_report(report: QualityReport) -> None:
    """Print the quality report for CLI users."""
    grade_color = {
        "A": "green",
        "B": "green",
        "C": "yellow",
        "D": "red",
        "F": "red",
    }.get(report.grade, "white")

    table = Table(
        title="Quality Report",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
    )
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    def _fmt_mean_std(mean: float, std: float, pct: bool = True) -> str:
        if report.runs <= 1:
            return f"{mean:.1%}" if pct else f"{mean:.0f}"
        if pct:
            return f"{mean:.1%} ± {std:.1%}"
        return f"{mean:.0f} ± {std:.0f}"

    table.add_row("Runs per test", str(report.runs))
    table.add_row("Seed (base)", str(report.seed if report.seed is not None else "—"))
    table.add_row(
        "Overall score",
        _fmt_mean_std(report.overall_score, report.overall_score_std),
    )
    table.add_row("Grade", f"[{grade_color}]{report.grade}[/]")
    if report.confidence_interval.get("overall_score"):
        ci = report.confidence_interval["overall_score"]
        table.add_row(
            "Overall 95% CI",
            f"{ci['ci_low']:.1%} – {ci['ci_high']:.1%} (n={ci['n']})",
        )
    table.add_row("Tests passed", f"{report.passed_tests}/{report.total_tests}")
    table.add_row(
        "Hallucination rate",
        _fmt_mean_std(report.hallucination_rate, report.hallucination_rate_std),
    )
    table.add_row(
        "Tool accuracy",
        _fmt_mean_std(report.tool_accuracy, report.tool_accuracy_std),
    )
    table.add_row(
        "Safety pass rate",
        _fmt_mean_std(report.safety_pass_rate, report.safety_pass_rate_std),
    )
    table.add_row(
        "Avg latency",
        _fmt_mean_std(report.avg_latency_ms, report.avg_latency_ms_std, pct=False) + " ms",
    )
    table.add_row("P95 latency", f"{report.p95_latency_ms:.0f} ms")
    table.add_row("Total tokens", str(report.total_tokens))

    console.print(table)

    if report.recommendations:
        console.print("\n[bold]Recommendations[/]")
        for rec in report.recommendations:
            console.print(f"  [dim]→[/] {rec}")

    console.print()


@cli.command()
def version():
    """Show AgentProbe version."""
    console.print("[bold blue]AgentProbe[/] v0.1.0")
    console.print("[dim]The first AI agent that tests other AI agents.[/]")


if __name__ == "__main__":
    cli()
