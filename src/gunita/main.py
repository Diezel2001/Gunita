"""Gunita CLI — entry point for all commands.

Usage:
    gunita webui                    Start server and open browser
    gunita serve                    Start server (headless)
    gunita status [--vault-path]    Show vault / Qdrant status
    gunita reindex [--vault-path]   Trigger incremental reindex
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from gunita.config import settings
from gunita.server import create_app

logger = logging.getLogger("gunita")

app = typer.Typer(
    name="gunita",
    help="Gunita — Web UI for the BFAI memory system",
    add_completion=False,
)


def _resolve_vault(vault_path: Path | None) -> None:
    """Resolve and set the vault path, ensuring it's absolute and exists."""
    if vault_path is not None:
        settings.bfai_vault_path = vault_path.resolve()
    else:
        settings.bfai_vault_path = settings.vault_path

    # Sync the resolved path to BFAI's env var so bfai internals (loader.py, db.py, etc.)
    # resolve the correct vault path instead of falling back to defaults.
    os.environ["BFAI_VAULT_PATH"] = str(settings.vault_path)

    # Ensure the vault directory exists
    settings.vault_path.mkdir(parents=True, exist_ok=True)
    (settings.vault_path / "notes").mkdir(parents=True, exist_ok=True)
    (settings.vault_path / "documents").mkdir(parents=True, exist_ok=True)
    (settings.vault_path / "images").mkdir(parents=True, exist_ok=True)
    (settings.vault_path / "metadata").mkdir(parents=True, exist_ok=True)


def _run_server(open_browser: bool = False) -> None:
    """Start the FastAPI/uvicorn server."""
    import uvicorn

    _do_reindex_on_empty()

    if open_browser:
        _open_browser(f"http://{settings.host}:{settings.port}")

    uvicorn.run(
        "gunita.server:create_app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        factory=True,
        log_level="info",
    )


def _do_reindex_on_empty() -> None:
    """Auto-reindex vault metadata if the database is empty."""
    from bfai.db import connect, ensure_schema, get_all_note_ids
    from bfai.sync import incremental_reindex

    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)
        note_ids = get_all_note_ids(conn)
        if not note_ids:
            print("  Database is empty — running initial reindex...")
            count = incremental_reindex(db_path=db_path)
            print(f"  Reindexed: {count} note(s)")
    finally:
        conn.close()


def _open_browser(url: str) -> None:
    """Open a URL in the default browser."""
    import webbrowser
    import threading

    def _open() -> None:
        import time
        time.sleep(1.0)  # Give the server a moment to start
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------


@app.command()
def webui(
    vault_path: Annotated[
        Optional[Path],
        typer.Option("--vault-path", "-v", help="Override the vault path"),
    ] = None,
) -> None:
    """Start the server and open the web UI in your browser."""
    _resolve_vault(vault_path)
    _run_server(open_browser=True)


@app.command()
def serve(
    vault_path: Annotated[
        Optional[Path],
        typer.Option("--vault-path", "-v", help="Override the vault path"),
    ] = None,
) -> None:
    """Start the API server (headless, no browser)."""
    _resolve_vault(vault_path)
    _run_server(open_browser=False)


@app.command()
def status(
    vault_path: Annotated[
        Optional[Path],
        typer.Option("--vault-path", "-v", help="Override the vault path"),
    ] = None,
) -> None:
    """Display vault and service status information."""
    from bfai.db import connect, ensure_schema, get_all_note_ids
    from bfai.sync import incremental_reindex
    from bfai.vault import get_vault, ensure_vault

    _resolve_vault(vault_path)

    vault = ensure_vault(settings.vault_path)
    conn = connect(settings.database_path)
    ensure_schema(conn)

    note_ids = get_all_note_ids(conn)
    note_count = len(note_ids)

    # Count relationships
    rel_count = 0
    for nid in note_ids:
        from bfai.db import get_relationships_for_note
        rels = get_relationships_for_note(conn, nid)
        rel_count += len(rels)

    conn.close()

    # Vault files (ensure_vault returns a Path, not a dict)
    notes_path = vault / "notes"
    md_files = list(notes_path.glob("*.md"))
    total_files = len(md_files)
    unindexed = total_files - note_count

    # Check Qdrant
    qdrant_ok = _check_qdrant()

    print()
    print("╔══════════════════════════════════════════╗")
    print("║          Gunita — System Status          ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║ Vault path  : {str(vault):>32s} ║")
    print(f"║ Notes in DB : {note_count:>32d} ║")
    print(f"║ Files on disk: {total_files:>32d} ║")
    print(f"║ Unindexed   : {unindexed:>32d} ║")
    print(f"║ Relationships: {rel_count:>32d} ║")
    print(f"║ Qdrant      : {'🟢 Connected' if qdrant_ok else '⚫ Unavailable':>32s} ║")
    print(f"║ Server      : http://{settings.host}:{settings.port:<17d} ║")
    print("╚══════════════════════════════════════════╝")
    print()


def _check_qdrant() -> bool:
    """Check if Qdrant is reachable."""
    try:
        import httpx
        r = httpx.get(f"{settings.qdrant_url}/collections", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


@app.command()
def reindex(
    vault_path: Annotated[
        Optional[Path],
        typer.Option("--vault-path", "-v", help="Override the vault path"),
    ] = None,
    embed: Annotated[
        bool,
        typer.Option("--embed", "-e", help="Generate vector embeddings for reindexed notes"),
    ] = False,
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", "-p", help="Embedding provider (sentence-transformers, ollama, openai)"),
    ] = None,
) -> None:
    """Trigger an incremental reindex of the vault."""
    from bfai.sync import incremental_reindex
    from bfai.vault import ensure_vault

    _resolve_vault(vault_path)

    vault = ensure_vault(settings.vault_path)
    print(f"Reindexing vault at {vault} ...")

    try:
        count = incremental_reindex(
            db_path=settings.database_path,
            embed=embed,
            provider_name=provider,
        )
        print(f"  Reindexed: {count} note(s)")
        if embed:
            print(f"  Embedding provider: {provider or 'default'}")
        print("Done.")
    except Exception as exc:
        print(f"Reindex failed: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from exc


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    app()