"""Watch command-line interface: serve, setup, doctor, watch, ui."""

from __future__ import annotations

import typer

app = typer.Typer(
    add_completion=False,
    help="Watch — give AI coding agents eyes. Turn videos into structured timelines.",
    no_args_is_help=True,
)

OPENROUTER = "https://openrouter.ai/api/v1"


def _notify_update() -> None:
    """Print an update notice to stderr (safe for interactive commands only)."""
    from .update import check

    notice = check()
    if notice:
        typer.secho(notice, fg=typer.colors.YELLOW, err=True)


@app.command()
def serve() -> None:
    """Run the MCP server over stdio (what MCP clients launch)."""
    from .server import main

    main()


@app.command()
def setup(
    api_key: str = typer.Option("", help="API key (skips the prompt)."),
    base_url: str = typer.Option("", help="OpenAI-compatible base URL."),
    model: str = typer.Option("", help="Sample-mode (image) model."),
    full_model: str = typer.Option("", help="Full-mode (video) model."),
    register: bool = typer.Option(True, help="Register with detected MCP clients."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Non-interactive; use defaults/flags."),
) -> None:
    """Configure Watch and register it with your MCP clients."""
    from . import clients
    from .config import write_config_file

    typer.secho("Watch setup", fg=typer.colors.CYAN, bold=True)

    base_url = base_url or (OPENROUTER if yes else typer.prompt("Base URL", default=OPENROUTER))
    if not api_key and not yes:
        api_key = typer.prompt("API key", hide_input=True, default="")
    if not model:
        model = "qwen/qwen3-vl-32b-instruct" if yes else typer.prompt(
            "Sample model (image)", default="qwen/qwen3-vl-32b-instruct")
    if not full_model:
        full_model = "qwen/qwen3.6-flash" if yes else typer.prompt(
            "Full model (video)", default="qwen/qwen3.6-flash")

    values = {"VLM_BASE_URL": base_url, "VLM_MODEL": model, "FULL_MODEL": full_model}
    if api_key:
        values["VLM_API_KEY"] = api_key
    path = write_config_file(values)
    typer.secho(f"[ok] Config saved to {path}", fg=typer.colors.GREEN)

    if register:
        typer.echo("\nRegistering with MCP clients:")
        for st in clients.register_all():
            mark = "[ok]" if st.registered else "[--]"
            color = typer.colors.GREEN if st.registered else typer.colors.YELLOW
            typer.secho(f"  {mark} {st.name}: {st.detail}", fg=color)

    typer.echo("\nRun 'watch-mcp doctor' to verify.")
    _notify_update()


@app.command()
def doctor() -> None:
    """Check ffmpeg, config, and client registration."""
    from . import clients
    from .config import CONFIG_FILE, get_settings
    from .ffmpeg import ffmpeg_path

    ok = True
    typer.secho("Watch doctor", fg=typer.colors.CYAN, bold=True)

    # ffmpeg
    try:
        fp = ffmpeg_path()
        typer.secho(f"  [ok] ffmpeg: {fp}", fg=typer.colors.GREEN)
    except Exception as e:  # noqa: BLE001
        ok = False
        typer.secho(f"  [X]  ffmpeg: {e}", fg=typer.colors.RED)

    # config
    s = get_settings()
    if s.use_stub:
        typer.secho("  [--] model: stub (no real model — run 'watch-mcp setup')",
                    fg=typer.colors.YELLOW)
    else:
        typer.secho(f"  [ok] model: {s.vlm_model} (full: {s.full_model or s.vlm_model})",
                    fg=typer.colors.GREEN)
        key = "set" if s.vlm_api_key else "MISSING"
        col = typer.colors.GREEN if s.vlm_api_key else typer.colors.RED
        typer.secho(f"  [{'ok' if s.vlm_api_key else 'X '}] api key: {key}", fg=col)
        ok = ok and bool(s.vlm_api_key)
    typer.echo(f"       config file: {CONFIG_FILE} ({'exists' if CONFIG_FILE.is_file() else 'none'})")

    # clients
    typer.echo("  clients:")
    for c in clients.detect():
        if not c.installed:
            typer.secho(f"    [--] {c.name}: not installed", fg=typer.colors.BRIGHT_BLACK)
        elif c.registered:
            typer.secho(f"    [ok] {c.name}: registered", fg=typer.colors.GREEN)
        else:
            typer.secho(f"    [--] {c.name}: installed, not registered", fg=typer.colors.YELLOW)

    _notify_update()
    raise typer.Exit(0 if ok else 1)


@app.command()
def watch(
    source: str = typer.Argument(..., help="Local path or URL."),
    mode: str = typer.Option("sample", help="sample | full | manual."),
    query: str = typer.Option("", help="What to focus on."),
) -> None:
    """Analyze one video and print the timeline JSON (handy for testing)."""
    import asyncio

    from .models import Mode
    from .pipeline import analyze

    result = asyncio.run(analyze(source, query=query or None, mode=Mode(mode)))
    typer.echo(result.model_dump_json(indent=2))


@app.command()
def ui() -> None:
    """Launch the terminal UI (configure + register clients)."""
    from .ui import WatchApp

    WatchApp().run()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
