"""Tests for the markdown loader module."""

import os
import tempfile
from pathlib import Path

import pytest

from bfai.loader import _notes_dir, list_notes, load_all_notes, load_note
from bfai.models import Note


class TestNoteModel:
    """Tests for the Note data model."""

    def test_title_defaults_to_stem(self):
        """Note title should default to filename stem when not provided."""
        path = Path("/vault/notes/project_x.md")
        note = Note(path=path, content="# Hello")
        assert note.title == "project_x"

    def test_title_explicit(self):
        """Explicit title should override the filename stem."""
        path = Path("/vault/notes/project_x.md")
        note = Note(path=path, content="# Hello", title="My Project")
        assert note.title == "My Project"

    def test_filename_property(self):
        """filename property should return the filename."""
        path = Path("/vault/notes/project_x.md")
        note = Note(path=path, content="")
        assert note.filename == "project_x.md"

    def test_extension_property(self):
        """extension property should return the file extension."""
        path = Path("/vault/notes/project_x.md")
        note = Note(path=path, content="")
        assert note.extension == ".md"

    def test_metadata_default_empty(self):
        """metadata should default to an empty dict."""
        note = Note(path=Path("/note.md"), content="")
        assert note.metadata == {}

    def test_id_auto_generated(self):
        """Note should auto-generate a UUID if not provided."""
        note = Note(path=Path("/note.md"), content="")
        assert note.id
        assert isinstance(note.id, str)
        assert len(note.id) == 32  # uuid4().hex is 32 chars

    def test_id_unique(self):
        """Each note should have a unique id."""
        note1 = Note(path=Path("/a.md"), content="")
        note2 = Note(path=Path("/b.md"), content="")
        assert note1.id != note2.id

    def test_id_preserved(self):
        """Explicit id should not be overwritten."""
        note = Note(path=Path("/note.md"), content="", id="custom-id-123")
        assert note.id == "custom-id-123"

    def test_created_at_default_none(self):
        """created_at should be None when not provided."""
        note = Note(path=Path("/note.md"), content="")
        assert note.created_at is None

    def test_updated_at_default_none(self):
        """updated_at should be None when not provided."""
        note = Note(path=Path("/note.md"), content="")
        assert note.updated_at is None


class TestListNotes:
    """Tests for discovering markdown files."""

    def test_list_notes_returns_sorted(self):
        """list_notes should return sorted markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            notes_dir = vault_path / "notes"
            notes_dir.mkdir(parents=True)

            # Create files in non-alphabetical order
            (notes_dir / "zeta.md").write_text("zeta")
            (notes_dir / "alpha.md").write_text("alpha")
            (notes_dir / "beta.md").write_text("beta")

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                paths = list_notes()
                assert len(paths) == 3
                assert paths[0].name == "alpha.md"
                assert paths[1].name == "beta.md"
                assert paths[2].name == "zeta.md"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_list_notes_only_markdown(self):
        """list_notes should only return .md files, ignoring other files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            notes_dir = vault_path / "notes"
            notes_dir.mkdir(parents=True)

            (notes_dir / "note.md").write_text("content")
            (notes_dir / "image.png").write_text("binary")
            (notes_dir / "note.txt").write_text("text")

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                paths = list_notes()
                assert len(paths) == 1
                assert paths[0].name == "note.md"
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_list_notes_no_notes_dir(self):
        """list_notes should return empty list if notes dir doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)  # No notes subdir created
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                paths = list_notes()
                assert paths == []
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_list_notes_empty_dir(self):
        """list_notes should return empty list when no .md files exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            (vault_path / "notes").mkdir()

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                paths = list_notes()
                assert paths == []
            finally:
                del os.environ["BFAI_VAULT_PATH"]


class TestLoadNote:
    """Tests for loading a single markdown file."""

    def test_load_note_success(self):
        """load_note should load content and return a Note object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_note.md"
            content = "# Hello World\n\nThis is a test note."
            filepath.write_text(content, encoding="utf-8")

            note = load_note(filepath)
            assert isinstance(note, Note)
            assert note.path == filepath.resolve()
            assert note.content == content
            # Title extracted from the # heading
            assert note.title == "Hello World"
            # Body should be the content without frontmatter
            assert note.body == content

    def test_load_note_with_frontmatter(self):
        """load_note should parse frontmatter and extract title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "project.md"
            content = "---\ntitle: My Project\ntags: test\n---\n# My Project\n\nDescription."
            filepath.write_text(content, encoding="utf-8")

            note = load_note(filepath)
            assert note.title == "My Project"
            assert note.metadata == {"title": "My Project", "tags": "test"}
            assert note.body == "# My Project\n\nDescription."
            assert note.content == content

    def test_load_note_with_frontmatter_title_only(self):
        """load_note should use frontmatter title when no heading."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "note.md"
            content = "---\ntitle: Custom Title\n---\n\nBody without heading."
            filepath.write_text(content, encoding="utf-8")

            note = load_note(filepath)
            assert note.title == "Custom Title"
            assert note.body == "\nBody without heading."

    def test_load_note_falls_back_to_stem(self):
        """load_note falls back to filename stem when no title found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "my_note.md"
            content = "Just a paragraph without a heading."
            filepath.write_text(content, encoding="utf-8")

            note = load_note(filepath)
            assert note.title == "my_note"

    def test_load_note_populates_updated_at(self):
        """load_note should populate updated_at from filesystem mtime."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test_note.md"
            filepath.write_text("# Hello", encoding="utf-8")

            note = load_note(filepath)
            assert note.updated_at is not None
            # updated_at should be close to current time
            import datetime
            now = datetime.datetime.now()
            diff = abs((now - note.updated_at).total_seconds())
            assert diff < 10  # Within 10 seconds

    def test_load_note_file_not_found(self):
        """load_note should raise FileNotFoundError for missing files."""
        path = Path("/tmp/nonexistent_note.md")
        with pytest.raises(FileNotFoundError):
            load_note(path)

    def test_load_note_invalid_extension(self):
        """load_note should raise ValueError for non-markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "image.png"
            filepath.write_text("not markdown")

            with pytest.raises(ValueError, match="Not a markdown file"):
                load_note(filepath)

    def test_load_note_case_insensitive_extension(self):
        """load_note should accept .MD uppercase extension."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "NOTE.MD"
            content = "# Uppercase"
            filepath.write_text(content, encoding="utf-8")

            note = load_note(filepath)
            assert note.content == content
            assert note.title == "Uppercase"

    def test_load_note_empty_file(self):
        """load_note should handle empty markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "empty.md"
            filepath.write_text("", encoding="utf-8")

            note = load_note(filepath)
            assert note.content == ""
            assert note.body == ""
            assert note.title == "empty"


class TestLoadAllNotes:
    """Tests for loading all notes from the vault."""

    def test_load_all_notes_success(self):
        """load_all_notes should load all markdown files in the notes dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            notes_dir = vault_path / "notes"
            notes_dir.mkdir(parents=True)

            (notes_dir / "alpha.md").write_text("# Alpha")
            (notes_dir / "beta.md").write_text("# Beta")

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                notes = load_all_notes()
                assert len(notes) == 2
                titles = {n.title for n in notes}
                # Titles are now extracted from the # heading
                assert titles == {"Alpha", "Beta"}
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_load_all_notes_empty_dir(self):
        """load_all_notes should return empty list for empty notes dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            (vault_path / "notes").mkdir()

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                notes = load_all_notes()
                assert notes == []
            finally:
                del os.environ["BFAI_VAULT_PATH"]

    def test_load_all_notes_skips_bad_files(self):
        """load_all_notes should skip non-markdown files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            notes_dir = vault_path / "notes"
            notes_dir.mkdir(parents=True)

            (notes_dir / "good.md").write_text("# Good")
            (notes_dir / "bad.txt").write_text("not md")

            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                notes = load_all_notes()
                assert len(notes) == 1
                # Title now extracted from the # heading
                assert notes[0].title == "Good"
            finally:
                del os.environ["BFAI_VAULT_PATH"]


class TestNotesDir:
    """Tests for the _notes_dir helper."""

    def test_notes_dir_resolves_to_vault_notes(self):
        """_notes_dir should return vault path + 'notes'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_path = Path(tmpdir)
            os.environ["BFAI_VAULT_PATH"] = str(vault_path)
            try:
                result = _notes_dir()
                assert result == vault_path / "notes"
            finally:
                del os.environ["BFAI_VAULT_PATH"]