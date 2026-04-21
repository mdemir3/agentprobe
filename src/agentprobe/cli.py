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
from agentprobe.probe.models import ConnectorType, TargetProfile

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
):
    if connector_type == "mcp":
        return MCPConnector(url=url, name=name, auth_token=auth_token)
    else:
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
def version():
    """Show AgentProbe version."""
    console.print("[bold blue]AgentProbe[/] v0.1.0")
    console.print("[dim]The first AI agent that tests other AI agents.[/]")


if __name__ == "__main__":
    cli()
