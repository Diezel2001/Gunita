"""watch.py — Watch the vault and automatically re-index changes."""
import time
import logging
from bfai.sync import FileWatcher, process_file_event
from bfai.vault import get_vault
from bfai.memory import index_note_from_path
from bfai.memory import delete as memory_delete
from bfai.writer import _resolve_note_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def on_file_event(event):
    """Callback invoked by the file watcher for each detected change."""
    if not event.is_markdown:
        return

    if event.event_type == "deleted":
        # Extract title from filename
        title = event.src_path.stem.replace("-", " ").title()
        result = memory_delete(title)
        logger.info("DELETED %s — db=%s", event.src_path.name, result["db_deleted"])

    elif event.event_type in ("created", "modified"):
        note_id = index_note_from_path(event.src_path)
        if note_id:
            logger.info("INDEXED %s → %s", event.src_path.name, note_id)
        else:
            logger.warning("FAILED %s", event.src_path.name)

    elif event.event_type == "renamed":
        # Index the new file, old will be handled by the deleted event
        note_id = index_note_from_path(event.dest_path)
        if note_id:
            logger.info("RENAMED → %s (%s)", event.dest_path.name, note_id)


def main():
    vault = get_vault()
    notes_dir = vault / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    watcher = FileWatcher(
        directory=str(notes_dir),
        callback=on_file_event,
        poll_interval=2.0,
    )

    print(f"Watching {notes_dir} for changes...")
    print("Press Ctrl+C to stop.")
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
    finally:
        watcher.stop()


if __name__ == "__main__":
    main()