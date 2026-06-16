"""ingest.py — Bulk import markdown files into BFAI.

Usage:
    python -m scripts.ingest [directory] [--vault-path PATH]

If no directory is given, imports all .md files from <vault>/notes/.
The --vault-path option overrides the BFAI_VAULT_PATH environment variable.
"""
import argparse
import sys
from pathlib import Path
from bfai.memory import index_note_from_path, reindex_all
from bfai.vault import ensure_vault


def ingest_directory(
    path: str,
    vault_path: str | None = None,
    embed: bool = False,
    provider_name: str | None = None,
) -> int:
    vault = Path(path)
    if not vault.exists():
        print(f"Error: {vault} does not exist")
        return 1

    md_files = list(vault.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files in {vault}")

    ensure_vault(vault_path)

    # Pre-initialise the embedding provider once (avoid reloading model
    # for each note).
    _embedding_provider = None
    if embed:
        from bfai.embeddings import get_provider
        _embedding_provider = get_provider(name=provider_name)

    success = 0
    embedded = 0
    for f in md_files:
        note_id = index_note_from_path(f)
        if note_id:
            print(f"  ✓ {f.name} → {note_id}")
            success += 1

            # Optionally generate embedding
            if embed:
                try:
                    from bfai.memory import _embed_note
                    from bfai.loader import load_note
                    from bfai.parser import parse_note
                    note = load_note(f)
                    parsed = parse_note(note.content)
                    note.id = note_id
                    note.title = parsed.title
                    note.body = parsed.body
                    _embed_note(note, provider=_embedding_provider)
                    embedded += 1
                except Exception as exc:
                    print(f"  ⚠ {f.name} — embedding failed: {exc}")
        else:
            print(f"  ✗ {f.name} — failed to index")

    print(f"\nIngested {success}/{len(md_files)} notes")
    if embed:
        print(f"Embedded {embedded}/{success} notes")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk import markdown files into BFAI")
    parser.add_argument(
        "directory",
        nargs="?",
        default=None,
        help="Directory to ingest from (default: <vault>/notes/)",
    )
    parser.add_argument(
        "--vault-path",
        "-v",
        default=None,
        help="Override the vault path (falls back to BFAI_VAULT_PATH env var)",
    )
    parser.add_argument(
        "--embed",
        "-e",
        action="store_true",
        default=False,
        help="Generate vector embeddings for ingested notes",
    )
    parser.add_argument(
        "--provider",
        "-p",
        default=None,
        help="Embedding provider (sentence-transformers, ollama, openai)",
    )
    args = parser.parse_args()

    from bfai.config import get_vault_path

    if args.directory:
        directory = args.directory
    else:
        vault_root = Path(args.vault_path) if args.vault_path else get_vault_path()
        directory = str(vault_root / "notes")

    sys.exit(ingest_directory(
        directory,
        vault_path=args.vault_path,
        embed=args.embed,
        provider_name=args.provider,
    ))
