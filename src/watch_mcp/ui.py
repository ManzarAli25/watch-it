"""Terminal UI for Watch setup: configure the model + register MCP clients."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Label, Static

from . import clients
from .config import read_config_file, write_config_file

OPENROUTER = "https://openrouter.ai/api/v1"


class WatchApp(App):
    """Configure Watch and register it with MCP clients, all in the terminal."""

    CSS = """
    Screen { align: center top; }
    #body { width: 90%; max-width: 90; padding: 1 2; }
    #banner { width: auto; margin: 0 0 1 0; }
    .h { text-style: bold; color: $accent; margin: 1 0 0 0; }
    .hint { color: $text-muted; margin: 0 0 1 0; }
    Input { margin: 0 0 1 0; }
    Label { margin: 1 0 0 0; }
    #status { margin: 1 0; color: $text-muted; }
    #clients { margin: 1 0; }
    .ok { color: $success; }
    .warn { color: $warning; }
    .off { color: $text-muted; }
    Horizontal { height: auto; }
    Button { margin: 1 1 0 0; }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        cfg = read_config_file()
        with VerticalScroll(id="body"):
            yield Static(self._banner(), id="banner")
            yield Static("Model configuration", classes="h")
            yield Static("OpenAI-compatible endpoint (e.g. OpenRouter).", classes="hint")

            yield Label("Base URL")
            yield Input(value=cfg.get("VLM_BASE_URL", OPENROUTER), id="base_url")
            yield Label("Sample model (image — for mode=sample)")
            yield Input(value=cfg.get("VLM_MODEL", "qwen/qwen3-vl-32b-instruct"), id="model")
            yield Label("Full model (video — for mode=full)")
            yield Input(value=cfg.get("FULL_MODEL", "qwen/qwen3.6-flash"), id="full_model")
            yield Label("API key")
            yield Input(value=cfg.get("VLM_API_KEY", ""), password=True, id="api_key")

            with Horizontal():
                yield Button("Save config", variant="primary", id="save")
            yield Static("", id="status")

            yield Static("MCP clients", classes="h")
            yield Static("Register Watch so agents can call it.", classes="hint")
            yield Static(id="clients")
            with Horizontal():
                yield Button("Detect", id="detect")
                yield Button("Register all", variant="success", id="register")
        yield Footer()

    def _banner(self):
        """Render the pixel-art banner; fall back to a title if anything fails."""
        try:
            from .banner import render_banner

            return render_banner(max_width=76, max_height=16)
        except Exception:  # noqa: BLE001 - never let the banner break the UI
            from rich.text import Text

            return Text("Watch — give AI coding agents eyes", style="bold")

    def on_mount(self) -> None:
        self._refresh_clients()
        # Check for updates off the UI thread; toast if one is available.
        self.run_worker(self._check_update, thread=True)

    def _check_update(self) -> None:
        from .update import check

        notice = check()
        if notice:
            self.call_from_thread(self.notify, notice, severity="warning", timeout=12)

    # --- actions ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "save":
            self._save()
        elif bid == "detect":
            self._refresh_clients()
        elif bid == "register":
            self._register_clients()

    def _save(self) -> None:
        values = {
            "VLM_BASE_URL": self.query_one("#base_url", Input).value.strip(),
            "VLM_MODEL": self.query_one("#model", Input).value.strip(),
            "FULL_MODEL": self.query_one("#full_model", Input).value.strip(),
            "VLM_API_KEY": self.query_one("#api_key", Input).value.strip(),
        }
        path = write_config_file(values)
        self.query_one("#status", Static).update(f"[green]✓ Saved to {path}[/]")

    def _refresh_clients(self) -> None:
        lines = []
        for c in clients.detect():
            if not c.installed:
                lines.append(f"[dim]• {c.name}: not installed[/]")
            elif c.registered:
                lines.append(f"[green]✓ {c.name}: registered[/]")
            else:
                lines.append(f"[yellow]• {c.name}: installed, not registered[/]")
        self.query_one("#clients", Static).update("\n".join(lines))

    def _register_clients(self) -> None:
        results = clients.register_all()
        lines = []
        for st in results:
            if st.registered:
                lines.append(f"[green]✓ {st.name}: {st.detail}[/]")
            elif not st.installed:
                lines.append(f"[dim]• {st.name}: {st.detail}[/]")
            else:
                lines.append(f"[yellow]• {st.name}: {st.detail}[/]")
        self.query_one("#clients", Static).update("\n".join(lines))
