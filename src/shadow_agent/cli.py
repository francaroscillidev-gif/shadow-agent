"""Shadow Agent CLI entrypoint."""
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from shadow_agent.core.config import load_config
from shadow_agent.proxy.server import create_app

app = typer.Typer(help="Shadow Agent - Local Privacy Guard & LLM Masking Proxy")
console = Console()

@app.command()
def start(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind"),
    port: int = typer.Option(8080, help="Port to listen on"),
    config_file: str = typer.Option(None, help="Path to shadow_agent.yaml configuration"),
):
    """Start the local privacy proxy server."""
    config = load_config(config_file)
    config.host = host
    config.port = port

    # Pretty startup banner
    info_table = Table.grid(padding=1)
    info_table.add_row("[bold cyan]Proxy URL:[/bold cyan]", f"http://{host}:{port}/v1")
    info_table.add_row("[bold cyan]Cloud Target:[/bold cyan]", f"{config.upstream.cloud_url} ({config.upstream.cloud_default_model})")
    info_table.add_row("[bold cyan]Local Target (Fallback):[/bold cyan]", f"{config.upstream.local_url} ({config.upstream.local_default_model})")
    info_table.add_row("[bold cyan]Synthetic Masking:[/bold cyan]", "[green]Enabled[/green]" if config.privacy.synthetic_replacement else "[yellow]Tokens[/yellow]")

    console.print(Panel(
        info_table,
        title="[bold green]🛡️ Shadow Agent Privacy Guard[/bold green]",
        subtitle="[dim]Drop-in OpenAI-Compatible Sidecar[/dim]",
        border_style="bright_blue"
    ))

    server_app = create_app(config)
    uvicorn.run(server_app, host=host, port=port, log_level="info")

@app.command()
def monitor(
    audit_file: str = typer.Option("shadow_audit.jsonl", help="Path to audit log file")
):
    """Launch real-time live terminal dashboard monitoring privacy metrics."""
    from shadow_agent.monitor import start_monitor
    start_monitor(audit_file)

@app.command()
def test_mask(
    text: str = typer.Argument(..., help="Sample prompt to test entity detection and masking")
):
    """Test regex & synthetic masking on a sample prompt in the terminal."""
    from shadow_agent.core.vault import EphemeralVault
    from shadow_agent.engine.masker import MaskingEngine
    from shadow_agent.engine.deanonymizer import DeAnonymizer

    vault = EphemeralVault()
    masker = MaskingEngine(use_synthetic=True)
    deanonymizer = DeAnonymizer(vault)

    masked_text, detected = masker.mask(text, vault)

    console.print("\n[bold yellow]Original Input:[/bold yellow]")
    console.print(text)

    console.print("\n[bold red]Detected Entities:[/bold red]")
    if not detected:
        console.print("[dim]None detected.[/dim]")
    else:
        for d in detected:
            console.print(f"- [bold magenta]{d.entity_type}[/bold magenta]: {d.original_value}")

    console.print("\n[bold green]Masked Text (Sent to Cloud):[/bold green]")
    console.print(masked_text)

    restored = deanonymizer.restore_batch(masked_text)
    console.print("\n[bold cyan]Restored Text (Local Reconstruction):[/bold cyan]")
    console.print(restored)
    console.print()

if __name__ == "__main__":
    app()
