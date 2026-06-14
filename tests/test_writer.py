"""Tests for the markdown writer module."""

import os
import tempfile
from pathlib import Path

import pytest

from bfai.loader import load_note
from bfai.models import Note
from bfai.writer import (
    _build_content,
    _metadata_to_frontmatter,
    _resolve_note_path,
    _slugify,
    create_note,
    delete_note,
    load_note_by_title,
    update_note,
)


class TestSlugify:
    """Tests for the _slugify helper."""

    def test_slugify_simple_title(self):
        """Simple title should be lowercased."""
        assert _slugify("Hello") == "hello"

    def test_slugify_spaces_to_hyphens(self):
        """Spaces should be replaced with hyphens."""
        assert _slugify("My Project") == "my-project"

    def test_slugify_special_characters(self):
        """Non-alphanumeric characters should be replaced."""
        assert _slugify("Hello! @World #2024") == "hello-world-2024"

    def test_slugify_collapses_multiple_hyphens(self):
        """Multiple consecutive hyphens should collapse to one."""
        assert _slugify("a---b") == "a-b"

    def test_slugify_strips_leading_trailing_hyphens(self):
        """Leading and trailing hyphens should be stripped."""
        assert _slugify("--hello--") == "hello"

    def test_slugify_preserves_underscores(self):
        """Underscores should be preserved."""
        assert _slugify("hello_world") == "hello_world"

    def test_slugify_preserves_hyphens(self):
        """Existing hyphens should be preserved."""
        assert _slugify("esp32-s3") == "esp32-s3"

    def test_slugify_empty_string(self):
        """Empty string should return 'untitled'."""
        assert _slugify("") == "untitled"

    def test_slugify_only_special_chars(self):
        """String with only special characters should return 'untitled'."""
        assert _slugify("!!!") == "untitled"

    def test_slugify_mixed_case(self):
        """Mixed case should be lowercased."""
        assert _slugify("ESP32 Project") == "esp32-project"


class TestMetadataToFrontmatter:
    """Tests for the _metadata_to_frontmatter helper."""

    def test_empty_metadata(self):
        """Empty metadata should return empty string."""
        assert _metadata_to_frontmatter({}) == ""

    def test_single_key(self):
        """Single key-value pair should produce frontmatter."""
        result = _metadata_to_frontmatter({"tags": "robotics"})
        expected = "---\ntags: robotics\n---\n"
        assert result == expected

    def test_multiple_keys(self):
        """Multiple key-value pairs should all appear in frontmatter."""
        result = _metadata_to_frontmatter({"tags": "robotics", "author": "Alice"})
        assert "tags: robotics" in result
        assert "author: Alice" in result
        assert result.startswith("---")
        assert result.endswith("---\n")


class TestBuildContent:
    """Tests for the _build_content helper."""

    def test_without_metadata(self):
        """Content without metadata should be returned as-is."""
        content = "# Hello\n\nBody text."
        assert _build_content(content, {}) == content

    def test_with_metadata(self):
        """Content with metadata should have frontmatter prepended."""
        content = "# Hello"
        result = _build_content(content, {"tags": "test"})
        assert result.startswith("---")
        assert "tags: test" in result
        assert result.endswith("---\n# Hello")


class TestResolveNotePath:
    """Tests for the _resolve_note_path helper."""

    def test_resolve_basic_title(self, monkeypatch):
        """Basic title should resolve to notes dir + slug + .md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            monkeypatch.setenv("BFAI_VAULT_PATH", str(vault_path))
            result = _resolve_note_path("My Project")
            assert result == vault_path / "notes" / "my-project.md"

    def test_resolve_preserves_case(self, monkeypatch):
        """Title case should be lowercased in the slug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            monkeypatch.setenv("BFAI_VAULT_PATH", str(vault_path))
            result = _resolve_note_path("ESP32-S3")
            assert result == vault_path / "notes" / "esp32-s3.md"


class TestCreateNote:
    """Tests for creating notes."""

    def test_create_note_basic(self):
        """create_note should create a file and return a Note object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Hello World", "# Hello\n\nWorld!")

                expected_path = vault_path / "notes" / "hello-world.md"
                assert note.path == expected_path
                assert note.content == "# Hello\n\nWorld!"
                assert note.title == "Hello World"
                assert expected_path.exists()
                assert expected_path.read_text(encoding="utf-8") == "# Hello\n\nWorld!"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_with_metadata(self):
        """create_note should write frontmatter when metadata is provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note(
                    "Tagged Note",
                    "# Tagged",
                    metadata={"tags": "test, python"},
                )

                assert note.metadata == {"tags": "test, python"}
                content = note.path.read_text(encoding="utf-8")
                assert content.startswith("---")
                assert "tags: test, python" in content
                assert content.endswith("---\n# Tagged")
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_exist_ok_false(self):
        """create_note should raise FileExistsError when note exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("Duplicate", "# First")
                with pytest.raises(FileExistsError, match="already exists"):
                    create_note("Duplicate", "# Second")
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_exist_ok_true(self):
        """create_note with exist_ok=True should overwrite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("Overwrite", "# First")
                note = create_note("Overwrite", "# Second", exist_ok=True)
                assert note.content == "# Second"
                assert note.path.read_text(encoding="utf-8") == "# Second"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_empty_content(self):
        """create_note should handle empty content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Empty", "")
                assert note.content == ""
                assert note.path.read_text(encoding="utf-8") == ""
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_special_chars_title(self):
        """create_note should slugify titles with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Hello! @World", "# Content")
                assert note.path.name == "hello-world.md"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_creates_notes_dir(self):
        """create_note should create the notes directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                # Notes directory does not exist yet
                notes_dir = vault_path / "notes"
                assert not notes_dir.exists()

                create_note("New Note", "# New")

                assert notes_dir.exists()
                assert notes_dir.is_dir()
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_returns_correct_note_object(self):
        """create_note should return a properly constructed Note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note(
                    "My Note",
                    "# Hello",
                    metadata={"author": "test"},
                )
                assert isinstance(note, Note)
                assert note.title == "My Note"
                assert note.content == "---\nauthor: test\n---\n# Hello"
                assert note.metadata == {"author": "test"}
                assert note.filename == "my-note.md"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_has_id(self):
        """create_note should assign a unique id to the note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("ID Test", "# Content")
                assert note.id
                assert isinstance(note.id, str)
                assert len(note.id) == 32
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_has_created_at(self):
        """create_note should set created_at to current time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                import datetime
                before = datetime.datetime.now()
                note = create_note("Created At Test", "# Content")
                after = datetime.datetime.now()
                assert note.created_at is not None
                assert before <= note.created_at <= after
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_create_note_has_updated_at(self):
        """create_note should set updated_at equal to created_at."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Updated At Test", "# Content")
                assert note.updated_at is not None
                assert note.updated_at == note.created_at
            finally:
                del os.environ["BFAI_VAULT_PATH"]


class TestUpdateNote:
    """Tests for updating notes."""

    def test_update_note_content(self):
        """update_note should update the file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Updatable", "# Original")
                updated = update_note(note, content="# Updated")

                assert updated.content == "# Updated"
                assert updated.path.read_text(encoding="utf-8") == "# Updated"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_no_content_arg(self):
        """update_note should use existing content when not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Unchanged", "# Original")
                updated = update_note(note)  # No content arg

                assert updated.content == "# Original"
                assert updated.path.read_text(encoding="utf-8") == "# Original"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_with_metadata_preserved(self):
        """update_note should preserve metadata and write frontmatter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note(
                    "Meta Update",
                    "# Original",
                    metadata={"tags": "test"},
                )
                updated = update_note(note, content="# Updated")

                assert updated.metadata == {"tags": "test"}
                file_content = updated.path.read_text(encoding="utf-8")
                assert "tags: test" in file_content
                assert file_content.endswith("---\n# Updated")
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_file_not_found(self):
        """update_note should raise FileNotFoundError for missing file."""
        note = Note(path=Path("/tmp/nonexistent.md"), content="content")
        with pytest.raises(FileNotFoundError):
            update_note(note)

    def test_update_note_invalid_extension(self):
        """update_note should raise ValueError for non-markdown paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "note.txt"
            filepath.write_text("content")
            note = Note(path=filepath, content="content")
            with pytest.raises(ValueError, match="Not a markdown file"):
                update_note(note)

    def test_update_note_preserves_title(self):
        """update_note should preserve the original title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Preserved Title", "# Original")
                updated = update_note(note, content="# Updated")
                assert updated.title == "Preserved Title"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_preserves_id(self):
        """update_note should preserve the original note id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("ID Preserve", "# Original")
                updated = update_note(note, content="# Updated")
                assert updated.id == note.id
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_preserves_created_at(self):
        """update_note should preserve the original created_at."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Created Preserve", "# Original")
                updated = update_note(note, content="# Updated")
                assert updated.created_at == note.created_at
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_update_note_updates_updated_at(self):
        """update_note should update the updated_at timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                import datetime
                note = create_note("Update Time", "# Original")
                # Small delay to ensure timestamp changes
                updated = update_note(note, content="# Updated")
                assert updated.updated_at is not None
                assert updated.updated_at > note.updated_at or updated.updated_at >= note.updated_at
            finally:
                del os.environ["BFAI_VAULT_PATH"]


class TestDeleteNote:
    """Tests for deleting notes."""

    def test_delete_note_by_note_object(self):
        """delete_note should remove the file when given a Note object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                note = create_note("Delete Me", "# Content")
                assert note.path.exists()

                delete_note(note)
                assert not note.path.exists()
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_delete_note_by_title(self):
        """delete_note should remove the file when given a title string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("By Title", "# Content")
                expected_path = vault_path / "notes" / "by-title.md"
                assert expected_path.exists()

                delete_note("By Title")
                assert not expected_path.exists()
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_delete_note_not_found(self):
        """delete_note should raise FileNotFoundError for missing note."""
        with pytest.raises(FileNotFoundError):
            delete_note("nonexistent-note")

    def test_delete_note_by_title_special_chars(self):
        """delete_note should slugify the title correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("Special! Title", "# Content")
                expected_path = vault_path / "notes" / "special-title.md"
                assert expected_path.exists()

                delete_note("Special! Title")
                assert not expected_path.exists()
            finally:
                del os.environ["BFAI_VAULT_PATH"]


class TestLoadNoteByTitle:
    """Tests for loading notes by title."""

    def test_load_note_by_title(self):
        """load_note_by_title should load an existing note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("Load Test", "# Loaded content")
                note = load_note_by_title("Load Test")

                # Title extracted from the # heading (Story 2.1)
                assert note.title == "Loaded content"
                assert note.content == "# Loaded content"
                assert note.body == "# Loaded content"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_load_note_by_title_not_found(self):
        """load_note_by_title should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_note_by_title("Does Not Exist")

    def test_load_note_by_title_slug_matches(self):
        """load_note_by_title should use slugified title for lookup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                create_note("My Project", "# Content")
                note = load_note_by_title("My Project")
                assert note.filename == "my-project.md"
            finally:
                del os.environ["BFAI_VAULT_PATH"]