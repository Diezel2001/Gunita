"""Tests for the vault synchronization module (Stories 9.1, 9.2)."""
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bfai.sync import (
    FileEvent,
    FileSnapshot,
    FileWatcher,
    _detect_changes,
    _snapshot_dir,
    incremental_reindex,
    process_file_event,
    process_file_events,
)


# ===========================================================================
# Tests: FileEvent
# ===========================================================================


class TestFileEvent:
    """Tests for the FileEvent dataclass."""

    def test_basic_event(self):
        """FileEvent should store event_type and src_path."""
        event = FileEvent(event_type="created", src_path=Path("/vault/test.md"))
        assert event.event_type == "created"
        assert event.src_path == Path("/vault/test.md")
        assert event.dest_path is None

    def test_rename_event(self):
        """FileEvent should store dest_path for renames."""
        event = FileEvent(
            event_type="renamed",
            src_path=Path("/vault/old.md"),
            dest_path=Path("/vault/new.md"),
        )
        assert event.dest_path == Path("/vault/new.md")

    def test_is_markdown(self):
        """is_markdown should check the extension."""
        assert FileEvent("created", Path("test.md")).is_markdown is True
        assert FileEvent("created", Path("test.MD")).is_markdown is True
        assert FileEvent("created", Path("test.txt")).is_markdown is False
        assert FileEvent("created", Path("test")).is_markdown is False


# ===========================================================================
# Tests: FileSnapshot
# ===========================================================================


class TestFileSnapshot:
    """Tests for the FileSnapshot dataclass."""

    def test_changed_since_different_mtime(self):
        """changed_since should detect mtime changes."""
        old = FileSnapshot(Path("test.md"), mtime=100.0, size=50)
        new = FileSnapshot(Path("test.md"), mtime=101.0, size=50)
        assert new.changed_since(old) is True

    def test_changed_since_different_size(self):
        """changed_since should detect size changes."""
        old = FileSnapshot(Path("test.md"), mtime=100.0, size=50)
        new = FileSnapshot(Path("test.md"), mtime=100.0, size=100)
        assert new.changed_since(old) is True

    def test_changed_since_identical(self):
        """changed_since should return False for identical snapshots."""
        old = FileSnapshot(Path("test.md"), mtime=100.0, size=50)
        new = FileSnapshot(Path("test.md"), mtime=100.0, size=50)
        assert new.changed_since(old) is False


# ===========================================================================
# Tests: _snapshot_dir
# ===========================================================================


class TestSnapshotDir:
    """Tests for the _snapshot_dir function."""

    def test_empty_directory(self, tmp_path):
        """Empty directory should produce empty snapshot."""
        snapshot = _snapshot_dir(tmp_path / "empty")
        assert snapshot == {}

    def test_snapshot_files(self, tmp_path):
        """Snapshot should capture files in the directory."""
        d = tmp_path / "notes"
        d.mkdir()
        (d / "a.md").write_text("hello")
        (d / "b.md").write_text("world")

        snapshot = _snapshot_dir(d)
        assert len(snapshot) == 2
        assert "a.md" in snapshot
        assert "b.md" in snapshot
        assert snapshot["a.md"].size == 5

    def test_snapshot_ignores_directories(self, tmp_path):
        """Snapshot should only include files, not subdirectories."""
        d = tmp_path / "notes"
        d.mkdir()
        (d / "sub").mkdir()
        (d / "note.md").write_text("content")

        snapshot = _snapshot_dir(d)
        assert len(snapshot) == 1
        assert "note.md" in snapshot

    def test_nonexistent_directory(self, tmp_path):
        """Nonexistent directory should return empty snapshot."""
        snapshot = _snapshot_dir(tmp_path / "nonexistent")
        assert snapshot == {}


# ===========================================================================
# Tests: _detect_changes
# ===========================================================================


class TestDetectChanges:
    """Tests for the _detect_changes function."""

    def test_no_changes(self):
        """No changes between identical snapshots."""
        old = {
            "a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10),
            "b.md": FileSnapshot(Path("/v/b.md"), 100.0, 20),
        }
        new = {
            "a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10),
            "b.md": FileSnapshot(Path("/v/b.md"), 100.0, 20),
        }
        events = _detect_changes(old, new)
        assert len(events) == 0

    def test_created_file(self):
        """New file should produce a 'created' event."""
        old = {"a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10)}
        new = {
            "a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10),
            "b.md": FileSnapshot(Path("/v/b.md"), 200.0, 20),
        }
        events = _detect_changes(old, new)
        assert len(events) == 1
        assert events[0].event_type == "created"
        assert events[0].src_path == Path("/v/b.md")

    def test_deleted_file(self):
        """Deleted file should produce a 'deleted' event."""
        old = {
            "a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10),
            "b.md": FileSnapshot(Path("/v/b.md"), 100.0, 20),
        }
        new = {"a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10)}
        events = _detect_changes(old, new)
        assert len(events) == 1
        assert events[0].event_type == "deleted"
        assert events[0].src_path == Path("/v/b.md")

    def test_modified_file(self):
        """Changed file should produce a 'modified' event."""
        old = {"a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10)}
        new = {"a.md": FileSnapshot(Path("/v/a.md"), 200.0, 20)}
        events = _detect_changes(old, new)
        assert len(events) == 1
        assert events[0].event_type == "modified"
        assert events[0].src_path == Path("/v/a.md")

    def test_multiple_events(self):
        """Multiple changes should produce multiple events."""
        old = {
            "a.md": FileSnapshot(Path("/v/a.md"), 100.0, 10),
            "b.md": FileSnapshot(Path("/v/b.md"), 100.0, 20),
        }
        new = {
            "b.md": FileSnapshot(Path("/v/b.md"), 150.0, 25),
            "c.md": FileSnapshot(Path("/v/c.md"), 100.0, 30),
        }
        events = _detect_changes(old, new)
        event_types = {e.event_type for e in events}
        assert "deleted" in event_types  # a.md
        assert "modified" in event_types  # b.md
        assert "created" in event_types  # c.md


# ===========================================================================
# Tests: process_file_event (with mocks)
# ===========================================================================


class TestProcessFileEvent:
    """Tests for the process_file_event function."""

    def test_skip_non_markdown(self):
        """Non-markdown files should be skipped."""
        event = FileEvent("created", Path("/v/test.txt"))
        result = process_file_event(event)
        assert result.get("skipped") is True

    def test_created_file(self, _clean_vault):
        """Created markdown file should be indexed."""
        notes_dir = _clean_vault / "notes"
        file_path = notes_dir / "test-note.md"
        file_path.write_text("# Test Note\n\nContent.")
        event = FileEvent("created", file_path)
        result = process_file_event(event)
        assert result["success"] is True
        assert "note_id" in result

    def test_modified_file(self, _clean_vault):
        """Modified markdown file should be re-indexed."""
        notes_dir = _clean_vault / "notes"
        file_path = notes_dir / "test-note.md"
        file_path.write_text("# Test Note\n\nOriginal content.")
        event = FileEvent("modified", file_path)
        result = process_file_event(event)
        assert result["success"] is True

    def test_deleted_file(self, _clean_vault):
        """Deleted file event should remove from index."""
        from bfai.memory import create

        # First create the note
        create("Delete Me", "Content to delete.")
        notes_dir = _clean_vault / "notes"
        file_path = notes_dir / "delete-me.md"

        # Now simulate deletion event (file exists but we're told it's deleted)
        event = FileEvent("deleted", file_path)
        result = process_file_event(event)
        assert result["success"] is True

    def test_renamed_file(self, _clean_vault):
        """Renamed file should be re-indexed at new path."""
        notes_dir = _clean_vault / "notes"
        old_path = notes_dir / "old-name.md"
        new_path = notes_dir / "new-name.md"
        old_path.write_text("# Old Name\n\nContent.")
        new_path.write_text("# New Name\n\nContent.")
        event = FileEvent("renamed", old_path, dest_path=new_path)
        result = process_file_event(event)
        assert result["success"] is True


# ===========================================================================
# Tests: process_file_events
# ===========================================================================


class TestProcessFileEvents:
    """Tests for the process_file_events function."""

    def test_batch_processing(self, _clean_vault):
        """Multiple events should all be processed."""
        notes_dir = _clean_vault / "notes"
        events = []
        for i in range(3):
            path = notes_dir / f"note-{i}.md"
            path.write_text(f"# Note {i}\n\nContent.")
            events.append(FileEvent("created", path))

        results = process_file_events(events)
        assert len(results) == 3
        assert all(r["success"] for r in results)


# ===========================================================================
# Tests: FileWatcher
# ===========================================================================


class TestFileWatcher:
    """Tests for the FileWatcher class."""

    def test_start_stop(self, tmp_path):
        """FileWatcher should start and stop cleanly."""
        callback = MagicMock()
        watcher = FileWatcher(callback, interval=0.5, directory=tmp_path)
        try:
            watcher.start()
            assert watcher.running is True
        finally:
            watcher.stop()
            assert watcher.running is False

    def test_detects_file_creation(self, tmp_path):
        """FileWatcher should detect new files."""
        events_collected = []
        callback = lambda e: events_collected.append(e)

        watcher = FileWatcher(callback, interval=0.2, directory=tmp_path)
        try:
            watcher.start()
            time.sleep(0.3)  # Initial scan

            # Create a file
            (tmp_path / "new-note.md").write_text("# New note")
            time.sleep(0.5)  # Wait for poll

            created = [e for e in events_collected if e.event_type == "created"]
            assert any("new-note.md" in str(e.src_path) for e in created)
        finally:
            watcher.stop()

    def test_ignores_non_markdown(self, tmp_path):
        """FileWatcher callback should still fire for non-markdown."""
        events_collected = []
        callback = lambda e: events_collected.append(e)

        watcher = FileWatcher(callback, interval=0.2, directory=tmp_path)
        try:
            watcher.start()
            time.sleep(0.3)

            (tmp_path / "readme.txt").write_text("text")
            time.sleep(0.5)

            created = [e for e in events_collected if e.event_type == "created"]
            assert any("readme.txt" in str(e.src_path) for e in created)
        finally:
            watcher.stop()

    def test_double_start(self, tmp_path):
        """Starting an already-running watcher should log a warning."""
        callback = MagicMock()
        watcher = FileWatcher(callback, interval=0.5, directory=tmp_path)
        try:
            watcher.start()
            watcher.start()  # Should not crash
            assert watcher.running is True
        finally:
            watcher.stop()


# ===========================================================================
# Tests: incremental_reindex
# ===========================================================================


class TestIncrementalReindex:
    """Tests for the incremental_reindex function."""

    def test_empty_vault(self, _clean_vault):
        """Empty vault should return 0."""
        count = incremental_reindex()
        assert count == 0

    def test_reindexes_new_files(self, _clean_vault):
        """New markdown files should be reindexed."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "note-a.md").write_text("# Note A\n\nContent.")
        (notes_dir / "note-b.md").write_text("# Note B\n\nContent.")

        count = incremental_reindex()
        assert count == 2

    def test_skips_unchanged_files(self, _clean_vault):
        """Unchanged files should be skipped."""
        from bfai.memory import create

        notes_dir = _clean_vault / "notes"

        # Index a note via create (sets updated_at)
        create("Unchanged Note", "Content.")

        # Incremental reindex should skip unchanged files
        count = incremental_reindex()
        assert count == 0

    def test_reindexes_modified_files(self, _clean_vault):
        """Modified files should be reindexed."""
        from bfai.memory import create

        notes_dir = _clean_vault / "notes"
        create("Modified Note", "Original content.")

        # Modify the file on disk (bypassing create)
        file_path = notes_dir / "modified-note.md"
        file_path.write_text("# Modified Note\n\nNew content.")
        time.sleep(0.1)  # Ensure mtime changes

        # Should detect and reindex the changed file
        count = incremental_reindex()
        assert count == 1

    def test_skips_non_markdown(self, _clean_vault):
        """Non-markdown files should be skipped."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "readme.txt").write_text("Not markdown")

        count = incremental_reindex()
        assert count == 0

    def test_callback_invoked(self, _clean_vault):
        """Callback should be invoked for each reindexed note."""
        notes_dir = _clean_vault / "notes"
        (notes_dir / "test-note.md").write_text("# Test Note\n\nContent.")

        results = []
        count = incremental_reindex(callback=lambda r: results.append(r))
        assert count == 1
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["title"] == "Test Note"


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def _clean_vault(monkeypatch, tmp_path):
    """Redirect the vault to a temporary directory for each test."""
    vault_dir = tmp_path / "vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    (vault_dir / "notes").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BFAI_VAULT_PATH", str(vault_dir))
    return vault_dir