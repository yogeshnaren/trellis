"""Trellis interactive CLI. Run with ``uv run trellis``."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from src.agent import Agent, AgentResult
from src.conversation import ConversationContext
from src.costs import MODEL_DEEPSEEK, get_shared_budget
from src.db import connect_readonly
from src.schema import get_schema, table_count

console = Console()


def _render(result: AgentResult, shared_remaining: float) -> None:
    if result.response_type in {"unsupported", "clarify"}:
        title = (
            "Unsupported question"
            if result.response_type == "unsupported"
            else "Clarification needed"
        )
        style = "yellow" if result.response_type == "unsupported" else "cyan"
        console.print(Panel(result.message or "", title=title, border_style=style))
    if result.sql:
        console.print(Panel(Syntax(result.sql, "sql"), title="Generated SQL"))
    if result.error:
        console.print(f"[red]{result.error_category}: {result.error}[/red]")
        console.print("Try rephrasing the question.")
        return
    rows = result.rows or []
    if result.response_type == "query":
        table = Table(show_header=True)
        for column in result.columns or []:
            table.add_column(column)
        for row in rows[:20]:
            table.add_row(*(str(value) if value is not None else "NULL" for value in row))
        console.print(table)
    suffix = f" · showing 20 of at least {len(rows)}" if len(rows) > 20 else ""
    repaired = " · ↻ repaired" if result.repaired else ""
    console.print(
        f"[dim]{result.t_total_ms / 1000:.2f}s · "
        f"{result.input_tokens} in ({result.cached_tokens} cached) / "
        f"{result.output_tokens} out · ${result.cost_usd:.6f} · "
        f"${shared_remaining:.4f} shared budget remaining{repaired}{suffix}[/dim]"
    )


async def _run() -> None:
    load_dotenv()
    db_path = Path(os.getenv("DB_PATH", "data/Chinook.db"))
    model = os.getenv("FIREWORKS_MODEL", MODEL_DEEPSEEK)
    ceiling = float(os.getenv("FIREWORKS_BUDGET_USD", "6.00"))
    session_allowance = float(os.getenv("SESSION_BUDGET_USD", "2.00"))
    guard = get_shared_budget(ceiling)
    connection = connect_readonly(db_path)
    context = ConversationContext(get_schema(db_path))
    agent = Agent(model, connection, guard, db_path=db_path)
    session_spent = 0.0
    last_sql: str | None = None
    console.print(
        Panel(
            f"Model: {model}\nDatabase: {db_path}\nTables: {table_count(db_path)}\n"
            f"Shared remaining: ${guard.remaining:.4f}",
            title="Trellis",
        )
    )
    try:
        while True:
            question = await asyncio.to_thread(console.input, "[bold cyan]Question:> [/bold cyan]")
            question = question.strip()
            if not question:
                continue
            if question.casefold() in {"exit", "quit"}:
                break
            if question == "/schema":
                console.print(get_schema(db_path))
                continue
            if question == "/clear":
                context.clear()
                console.print("[dim]Conversation cleared.[/dim]")
                continue
            if question == "/last":
                console.print(last_sql or "[dim]No SQL generated yet.[/dim]")
                continue
            if guard.remaining <= 0:
                console.print("[red]Shared project budget exhausted; refusing a new query.[/red]")
                continue
            if session_spent >= session_allowance:
                console.print(
                    f"[yellow]This CLI session's ${session_allowance:.2f} "
                    "soft allowance is exhausted.[/yellow]"
                )
                continue
            if not os.getenv("FIREWORKS_API_KEY"):
                console.print(
                    "[red]FIREWORKS_API_KEY is not set. Export it before querying.[/red]"
                )
                continue
            with console.status("Generating and validating SQL..."):
                result = await agent.ask(question, context)
            session_spent += result.cost_usd
            last_sql = result.sql or last_sql
            _render(result, guard.remaining)
    finally:
        connection.close()


def main() -> None:
    try:
        asyncio.run(_run())
    except (EOFError, KeyboardInterrupt):
        console.print("\nGoodbye.")


if __name__ == "__main__":
    main()
