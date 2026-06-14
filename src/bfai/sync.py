"""Vault synchronization module for BFAI.

Provides file watching and incremental reindexing to keep the database
and indexes synchronized with the filesystem.

Uses a polling-based approach (no external dependencies) to detect
file system changes. The polling interval is configurable.

Stories implemented:
- 9.1 File Watcher — Detect create, modify, delete, rename events
- 9.2 Incremental Reindexing — Reprocess only changed notes
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Event, Thread
from typing import Callable

from bfai.loader import _notes_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FileEvent:
    """Represents a single file system event detected by the watcher.

    Attributes:
        event_type: One of ``"created"``, ``"modified"``, ``"deleted"``,
            or ``"renamed"``.
        src_path: Absolute path of the affected file.
        dest_path: For rename events, the new path. ``None`` for other
            event types.
    """

    event_type: str
    src_path: Path
    dest_path: Path | None = None

    @property
    def is_markdown(self) -> bool:
        """``True`` if the file has a ``.md`` extension (case-insensitive)."""
        return self.src_path.suffix.lower() == ".md"


# ---------------------------------------------------------------------------
# File system snapshot
# ---------------------------------------------------------------------------


@dataclass
class FileSnapshot:
    """A snapshot of a file's metadata for change detection.

    Attributes:
        path: The file's absolute path.
        mtime: Last modification timestamp (from ``os.stat``).
        size: File size in bytes.
    """

    path: Path
    mtime: float
    size: int

    def changed_since(self, other: FileSnapshot) -> bool:
        """Check if this snapshot differs from another.

        Returns:
            ``True`` if mtime or size has changed.
        """
        return self.mtime != other.mtime or self.size != other.size


def _snapshot_dir(directory: Path) -> dict[str, FileSnapshot]:
    """Take a snapshot of all files in a directory.

    Args:
        directory: The directory to scan.

    Returns:
        A dict mapping filename (basename) to its ``FileSnapshot``.
    """
    snapshot: dict[str, FileSnapshot] = {}
    if not directory.exists():
        return snapshot

    try:
        for entry in os.scandir(str(directory)):
            if entry.is_file():
                stat = entry.stat()
                snapshot[entry.name] = FileSnapshot(
                    path=Path(entry.path),
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                )
    except PermissionError as exc:
        logger.warning("Permission denied scanning directory %s: %s", directory, exc)
    except OSError as exc:
        logger.warning("Error scanning directory %s: %s", directory, exc)

    return snapshot


def _detect_changes(
    old: dict[str, FileSnapshot],
    new: dict[str, FileSnapshot],
) -> list[FileEvent]:
    """Compare two snapshots and produce a list of file events.

    Detects:
    - Created: files in ``new`` but not in ``old``
    - Deleted: files in ``old`` but not in ``new``
    - Modified: files in both with different mtime or size
    - Renamed: a delete + create pair where size matches and mtimes
      are close (within 1 second)

    Args:
        old: The previous snapshot.
        new: The current snapshot.

    Returns:
        A list of ``FileEvent`` objects describing the changes.
    """
    events: list[FileEvent] = []

    old_names = set(old.keys())
    new_names = set(new.keys())

    # Created files
    for name in new_names - old_names:
        events.append(FileEvent(
            event_type="created",
            src_path=new[name].path,
        ))

    # Deleted files
    for name in old_names - new_names:
        events.append(FileEvent(
            event_type="deleted",
            src_path=old[name].path,
        ))

    # Modified files
    for name in old_names & new_names:
        if new[name].changed_since(old[name]):
            events.append(FileEvent(
                event_type="modified",
                src_path=new[name].path,
            ))

    # Rename detection: look for size+mtime matches between deleted and created
    created_by_name = {e.src_path.name: e for e in events if e.event_type == "created"}
    deleted_by_name = {e.src_path.name: e for e in events if e.event_type == "deleted"}

    consumed_created: set[str] = set()
    renamed_events: list[FileEvent] = []

    for name, del_event in deleted_by_name.items():
        if name in created_by_name:
            continue
        old_snap = old.get(name)
        if old_snap is None:
            continue
        for cname, cre_event in created_by_name.items():
            if cname in consumed_created:
                continue
            new_snap = new.get(cname)
            if new_snap is None:
                continue
            if (new_snap.size == old_snap.size
                    and abs(new_snap.mtime - old_snap.mtime) < 1.0):
                renamed_events.append(FileEvent(
                    event_type="renamed",
                    src_path=del_event.src_path,
                    dest_path=cre_event.src_path,
                ))
                consumed_created.add(cname)
                break

    # Build result: exclude consumed created events, add rename events
    result: list[FileEvent] = [
        e for e in events
        if not (e.event_type == "created" and e.src_path.name in consumed_created)
    ]
    result.extend(renamed_events)
    return result


# ---------------------------------------------------------------------------
# File watcher
# ---------------------------------------------------------------------------


class FileWatcher:
    """Polling-based file system watcher for the vault.

    Periodically scans the vault's notes directory and emits events
    when files are created, modified, deleted, or renamed.

    The watcher runs in its own thread and calls a user-provided
    callback for each detected event.

    Args:
        callback: A callable that accepts a ``FileEvent``. Called for
            each detected change.
        interval: Polling interval in seconds (default 2.0).
        directory: The directory to watch. Defaults to the vault's
            notes directory.
    """

    def __init__(
        self,
        callback: Callable[[FileEvent], None],
        interval: float = 2.0,
        directory: Path | None = None,
    ) -> None:
        self.callback = callback
        self.interval = interval
        self.directory = directory or _notes_dir()
        self._snapshot: dict[str, FileSnapshot] = {}
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the watcher in a background thread.

        The first scan initialises the snapshot without firing any
        events. Subsequent scans detect and report changes.
        """
        if self._thread is not None and self._thread.is_alive():
            logger.warning("FileWatcher is already running")
            return

        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="bfai-watcher",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "FileWatcher started (interval=%ss, directory=%s)",
            self.interval,
            self.directory,
        )

    def stop(self) -> None:
        """Stop the watcher and wait for the thread to exit."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        logger.info("FileWatcher stopped")

    @property
    def running(self) -> bool:
        """``True`` if the watcher thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        """Main polling loop. Runs in a background thread."""
        try:
            self._snapshot = _snapshot_dir(self.directory)
        except OSError as exc:
            logger.error("Failed to scan vault directory: %s", exc)
            return

        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.interval)
            if self._stop_event.is_set():
                break

            try:
                new_snapshot = _snapshot_dir(self.directory)
                events = _detect_changes(self._snapshot, new_snapshot)
                self._snapshot = new_snapshot

                for event in events:
                    try:
                        self.callback(event)
                    except Exception as exc:
                        logger.error(
                            "Error in file watcher callback for %s: %s",
                            event.src_path,
                            exc,
                        )
            except OSError as exc:
                logger.warning("Error during vault scan: %s", exc)


# ---------------------------------------------------------------------------
# Event processing
# ---------------------------------------------------------------------------


def process_file_event(event: FileEvent) -> dict:
    """Process a single file event by updating the database and indexes.

    For created/modified events, indexes the note. For deleted events,
    removes it from the database. For renamed events, re-indexes at the
    new path.

    Args:
        event: The file event to process.

    Returns:
        Dict with keys ``event_type``, ``path``, ``success``, and
        optional ``note_id`` and ``error``.
    """
    from bfai.memory import index_note_from_path, delete as memory_delete

    result: dict = {
        "event_type": event.event_type,
        "path": str(event.src_path),
        "success": False,
    }

    if not event.is_markdown:
        result["skipped"] = True
        return result

    try:
        if event.event_type in ("created", "modified"):
            note_id = index_note_from_path(event.src_path)
            if note_id:
                result["success"] = True
                result["note_id"] = note_id
            else:
                result["error"] = "Failed to index note"
        elif event.event_type == "deleted":
            title = event.src_path.stem
            delete_result = memory_delete(title)
            result["success"] = delete_result.get("success", False)
            if not result["success"]:
                result["error"] = delete_result.get("error", "Delete failed")
        elif event.event_type == "renamed":
            if event.dest_path:
                note_id = index_note_from_path(event.dest_path)
                if note_id:
                    result["success"] = True
                    result["note_id"] = note_id
                else:
                    result["error"] = "Failed to index renamed note"
        else:
            result["error"] = f"Unknown event type: {event.event_type}"
    except Exception as exc:
        result["error"] = str(exc)
        logger.error("Error processing %s for %s: %s", event.event_type, event.src_path, exc)

    return result


def process_file_events(
    events: list[FileEvent],
    *,
    fail_fast: bool = False,
) -> list[dict]:
    """Process a batch of file events.

    Args:
        events: List of file events to process.
        fail_fast: If ``True``, stop processing on the first failure
            (default ``False``).

    Returns:
        List of result dicts (one per event).
    """
    results: list[dict] = []
    for event in events:
        result = process_file_event(event)
        results.append(result)
        if fail_fast and not result.get("success") and not result.get("skipped"):
            break
    return results


# ---------------------------------------------------------------------------
# Incremental reindexing
# ---------------------------------------------------------------------------


def incremental_reindex(
    callback: Callable[[dict], None] | None = None,
    embed: bool = False,
    provider_name: str | None = None,
    db_path: Path | None = None,
) -> int:
    """Perform an incremental reindex of the vault.

    Scans the vault's notes directory and re-indexes only files that
    have changed since the last index. Change detection is based on
    comparing current mtime/size against the database's stored
    ``updated_at`` timestamp.

    When ``embed`` is ``True``, each reindexed note also gets an
    embedding generated and stored in the Qdrant vector store.
    Only changed notes are embedded — unchanged notes are skipped.

    Args:
        callback: Optional callable invoked for each reindexed note
            with a result dict.
        embed: Whether to generate vector embeddings for reindexed
            notes (default ``False``). Requires a running Qdrant
            instance and an embedding provider.
        provider_name: Embedding provider name (e.g. ``"openai"``,
            ``"ollama"``, ``"sentence-transformers"``). Only used
            when ``embed`` is ``True``.
        db_path: Optional explicit path to the SQLite database file.
            If not provided, falls back to ``connect()`` with no args
            (which resolves via ``BFAI_VAULT_PATH`` env var or
            defaults to ``./vault``).

    Returns:
        The number of notes reindexed.
    """
    from bfai.db import (
        connect,
        ensure_schema,
        get_all_note_ids,
        get_note_by_id,
        get_note_by_path as db_get_note_by_path,
        upsert_note,
        index_note_fts,
        process_wiki_links,
        store_tags,
        delete_note_by_id,
        delete_note_fts,
    )
    from bfai.loader import load_note
    from bfai.parser import parse_note

    notes_dir = _notes_dir()
    if not notes_dir.exists():
        logger.warning("Notes directory does not exist: %s", notes_dir)
        return 0

    reindexed = 0
    embedded = 0
    conn = connect(db_path)
    try:
        ensure_schema(conn)

        # Get current file snapshots
        current_files = _snapshot_dir(notes_dir)

        # Get all existing note IDs from the database
        existing_ids = get_all_note_ids(conn)

        # Check each markdown file in the vault
        for filename, snap in current_files.items():
            if not filename.lower().endswith(".md"):
                continue

            file_path = snap.path
            file_mtime = datetime.fromtimestamp(snap.mtime)

            # Try to find the note in the database by path
            path_str = str(file_path.resolve())
            note_record = db_get_note_by_path(conn, path_str)

            if note_record:
                db_updated = note_record.get("updated_at")
                if db_updated:
                    try:
                        if isinstance(db_updated, str):
                            db_dt = datetime.fromisoformat(db_updated)
                        else:
                            db_dt = db_updated
                        if file_mtime <= db_dt:
                            continue
                    except (ValueError, TypeError):
                        pass

            # Load and reindex the note
            try:
                note = load_note(file_path)
                parsed = parse_note(note.content)
                note.title = parsed.title
                note.body = parsed.body
                note.metadata = parsed.metadata
                note.tags = parsed.tags
                note.wiki_links = parsed.wiki_links
                note.entities = parsed.entities

                stored_id = upsert_note(conn, note)
                note.id = stored_id
                index_note_fts(conn, stored_id, note.title, note.body or note.content)

                if note.wiki_links:
                    process_wiki_links(conn, note)
                if note.tags:
                    store_tags(conn, stored_id, note.tags)

                reindexed += 1

                # Optionally generate embedding for the reindexed note
                if embed:
                    try:
                        from bfai.memory import _embed_note
                        _embed_note(note, provider_name=provider_name)
                        embedded += 1
                    except Exception as embed_exc:
                        logger.warning(
                            "Failed to embed note '%s': %s", note.title, embed_exc
                        )

                if callback:
                    callback({
                        "success": True,
                        "note_id": stored_id,
                        "title": note.title,
                        "path": str(file_path),
                    })

            except (FileNotFoundError, ValueError, OSError) as exc:
                logger.warning("Failed to incrementally reindex %s: %s", filename, exc)
                if callback:
                    callback({
                        "success": False,
                        "path": str(file_path),
                        "error": str(exc),
                    })

        # Handle deleted files: note exists in DB but not on disk
        for nid in existing_ids:
            note = get_note_by_id(conn, nid)
            if note and note["path"]:
                note_path = Path(note["path"])
                if not note_path.exists():
                    delete_note_fts(conn, nid)
                    delete_note_by_id(conn, nid)
                    logger.info("Removed deleted note from index: %s", note["title"])

        if embed:
            logger.info(
                "Incremental reindex complete: %d note(s) reindexed, %d embedded",
                reindexed,
                embedded,
            )
        else:
            logger.info("Incremental reindex complete: %d note(s) processed", reindexed)
        return reindexed
    finally:
        conn.close()