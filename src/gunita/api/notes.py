"""Note endpoints.

GET    /api/notes/                    — List all notes (with pagination)
GET    /api/notes/{note_id}           — Get full note detail
GET    /api/notes/{note_id}/backlinks — Get backlinks for a note
POST   /api/notes/                    — Create a new note
PUT    /api/notes/{note_id}           — Update an existing note
DELETE /api/notes/{note_id}           — Delete a note
GET    /api/notes/{note_id}/versions  — List note versions
GET    /api/notes/{note_id}/diff      — Compare two versions
"""

from __future__ import annotations

import difflib
import hashlib
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class NoteSummary(BaseModel):
    """Lightweight note representation for listing."""
    note_id: str
    title: str
    path: str
    tags: list[str] = []


class NoteDetail(NoteSummary):
    """Full note detail including content and metadata."""
    content: str = ""
    metadata: dict[str, str] = {}
    created_at: str | None = None
    updated_at: str | None = None


class NoteListResponse(BaseModel):
    """Paginated note list."""
    notes: list[NoteSummary]
    total: int
    offset: int
    limit: int


class BacklinkItem(BaseModel):
    """A single backlink reference."""
    note_id: str
    title: str
    rel_type: str


class NoteCreateRequest(BaseModel):
    """Request body for creating a note."""
    title: str
    content: str
    tags: list[str] = []
    metadata: dict[str, str] = {}


class NoteUpdateRequest(BaseModel):
    """Request body for updating a note."""
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, str] | None = None


class NoteCreateResponse(BaseModel):
    """Response after creating a note."""
    note_id: str
    title: str
    path: str
    message: str = "Note created successfully"


class NoteVersion(BaseModel):
    """A single version snapshot of a note."""
    version: int
    content_hash: str
    saved_at: str
    content_length: int


class NoteVersionsResponse(BaseModel):
    """List of note versions."""
    note_id: str
    versions: list[NoteVersion]


class DiffLine(BaseModel):
    """A single line in a diff."""
    type: str  # "added", "removed", "unchanged"
    content: str
    old_line: int | None = None
    new_line: int | None = None


class DiffResponse(BaseModel):
    """Diff between two versions."""
    old_version: int
    new_version: int
    lines: list[DiffLine]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content_hash(content: str) -> str:
    """Compute a short SHA-256 hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _get_versions_dir(note_path: Path) -> Path:
    """Get or create the versions directory for a note."""
    # Store versions in vault/metadata/versions/{note_stem}/
    vault_metadata = note_path.parent.parent / "metadata"
    versions_dir = vault_metadata / "versions" / note_path.stem
    versions_dir.mkdir(parents=True, exist_ok=True)
    return versions_dir


def _save_version(note_path: Path, content: str) -> int:
    """Save a version snapshot of the note content.

    Returns the version number.
    """
    versions_dir = _get_versions_dir(note_path)
    # Find existing versions
    existing = sorted(versions_dir.glob("v*.md"), key=lambda p: p.name)
    version_num = len(existing) + 1

    version_file = versions_dir / f"v{version_num}.md"
    version_file.write_text(content, encoding="utf-8")

    # Also save metadata alongside
    meta_file = versions_dir / f"v{version_num}.meta"
    now = datetime.now().isoformat()
    meta_file.write_text(
        f"version: {version_num}\n"
        f"saved_at: {now}\n"
        f"content_hash: {_content_hash(content)}\n"
        f"content_length: {len(content)}\n",
        encoding="utf-8",
    )
    return version_num


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=NoteListResponse)
async def list_notes(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> NoteListResponse:
    """List all indexed notes with pagination."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_all_note_ids, get_note_by_id, get_tags_for_note

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)
        all_ids = get_all_note_ids(conn)
        total = len(all_ids)
        paginated_ids = all_ids[offset:offset + limit]

        notes: list[NoteSummary] = []
        for nid in paginated_ids:
            note = get_note_by_id(conn, nid)
            if not note:
                continue
            tags = get_tags_for_note(conn, nid)
            notes.append(NoteSummary(
                note_id=nid,
                title=note.get("title", "") or "",
                path=note.get("path", "") or "",
                tags=tags,
            ))

        return NoteListResponse(
            notes=notes,
            total=total,
            offset=offset,
            limit=limit,
        )
    finally:
        conn.close()


@router.get("/{note_id}", response_model=NoteDetail)
async def get_note(note_id: str) -> NoteDetail:
    """Get full detail for a single note including content."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id, get_tags_for_note

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_record = get_note_by_id(conn, note_id)
        if not note_record:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        tags = get_tags_for_note(conn, note_id)

        # Load the note content from disk
        note_path = note_record.get("path", "")
        content = ""
        metadata: dict[str, str] = {}

        if note_path:
            file_path = Path(note_path)
            if file_path.exists() and file_path.suffix.lower() == ".md":
                try:
                    from bfai.loader import load_note
                    loaded = load_note(file_path)
                    content = loaded.content
                    metadata = loaded.metadata
                except (FileNotFoundError, ValueError, OSError):
                    content = f"(Could not load file: {note_path})"

        return NoteDetail(
            note_id=note_id,
            title=note_record.get("title", "") or "",
            path=note_path,
            tags=tags,
            content=content,
            metadata=metadata,
            created_at=note_record.get("created_at"),
            updated_at=note_record.get("updated_at"),
        )
    finally:
        conn.close()


@router.get("/{note_id}/backlinks", response_model=list[BacklinkItem])
async def get_backlinks(note_id: str) -> list[BacklinkItem]:
    """Get all notes that link to the given note."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id, get_backlinks as db_get_backlinks

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        # Verify the note exists
        note = get_note_by_id(conn, note_id)
        if not note:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        try:
            backlinks = db_get_backlinks(conn, note_id)
        except ValueError:
            return []

        return [
            BacklinkItem(
                note_id=bl["related_note_id"] or "",
                title=bl["related_title"] or "",
                rel_type=bl["relationship_type"] or "",
            )
            for bl in backlinks
        ]
    finally:
        conn.close()


# ─── Create / Update / Delete ────────────────────────────────────────────

@router.post("/", response_model=NoteCreateResponse)
async def create_note(req: NoteCreateRequest) -> NoteCreateResponse:
    """Create a new note in the vault."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, upsert_note, store_tags, index_note_fts, process_wiki_links
    from bfai.models import Note
    from bfai.memory import _resolve_incoming_wiki_links

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        # Create the note file on disk via bfai.writer
        from bfai.writer import create_note as bfai_create_note
        from bfai.parser import parse_note as bfai_parse_note

        try:
            created = bfai_create_note(
                title=req.title,
                content=req.content,
                metadata=req.metadata or {},
                exist_ok=False,
            )
        except FileExistsError:
            raise HTTPException(status_code=409, detail=f"Note '{req.title}' already exists")

        # Parse the created file to get tags and wiki links
        parsed = bfai_parse_note(created.path)

        # Store in database
        note_id = upsert_note(conn, created)

        # Store tags
        all_tags = list(set(parsed.tags + req.tags))
        store_tags(conn, note_id, all_tags)

        # Index in FTS
        index_note_fts(conn, note_id, created.title, parsed.body or created.content)

        # Build a proper Note object from the parsed result and created data
        note_obj = Note(
            path=created.path,
            content=created.content,
            body=parsed.body or created.content,
            id=note_id,
            title=created.title,
            metadata=parsed.metadata or {},
            tags=parsed.tags,
            wiki_links=parsed.wiki_links,
            entities=parsed.entities,
        )

        # Process wiki links → relationships
        process_wiki_links(conn, note_obj)

        # Resolve incoming wiki links from other notes that link to this one
        _resolve_incoming_wiki_links(conn, note_obj)

        # Save first version
        _save_version(created.path, created.content)

        return NoteCreateResponse(
            note_id=note_id,
            title=created.title,
            path=str(created.path),
            message="Note created successfully",
        )
    finally:
        conn.close()


@router.put("/{note_id}", response_model=NoteDetail)
async def update_note(note_id: str, req: NoteUpdateRequest) -> NoteDetail:
    """Update an existing note's content, title, or tags."""
    from gunita.config import settings
    from bfai.db import (
        connect, ensure_schema, get_note_by_id, get_tags_for_note,
        upsert_note, store_tags, index_note_fts, process_wiki_links,
        delete_note_by_id as db_delete_note,
    )
    from bfai.models import Note
    from bfai.memory import _resolve_incoming_wiki_links

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_record = get_note_by_id(conn, note_id)
        if not note_record:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        note_path = note_record.get("path", "")
        if not note_path:
            raise HTTPException(status_code=500, detail="Note has no file path")

        file_path = Path(note_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Note file not found on disk")

        # Load existing note
        from bfai.loader import load_note
        loaded = load_note(file_path)

        # Update content if provided
        new_content = req.content if req.content is not None else loaded.content

        # Save version before updating
        _save_version(file_path, new_content)

        # Update on disk via bfai.writer
        from bfai.writer import update_note as bfai_update_note
        updated = bfai_update_note(loaded, content=new_content)

        # Re-parse the note
        from bfai.parser import parse_note as bfai_parse_note
        parsed = bfai_parse_note(updated.path)

        # Re-upsert in database (updates title and timestamp)
        # If title changed, delete old record first
        old_title = note_record.get("title", "")
        new_title = req.title if req.title is not None else old_title

        if req.title is not None and req.title != old_title:
            # Delete old note record and re-insert with new path
            db_delete_note(conn, note_id)
            from bfai.writer import create_note as bfai_create_note
            # Rename file if title changed
            from bfai.writer import _resolve_note_path
            new_path = _resolve_note_path(new_title)
            if file_path != new_path:
                file_path.rename(new_path)
                updated.path = new_path
                # Re-parse with new path
                parsed = bfai_parse_note(new_path)

            new_note_id = upsert_note(conn, updated)
        else:
            new_note_id = upsert_note(conn, updated)

        # Update tags
        tag_set = list(set(parsed.tags + (req.tags or [])))
        store_tags(conn, new_note_id, tag_set)

        # Re-index FTS
        index_note_fts(conn, new_note_id, new_title, parsed.body or new_content)

        # Build a proper Note object from the parsed result
        note_obj = Note(
            path=updated.path,
            content=new_content,
            body=parsed.body or new_content,
            id=new_note_id,
            title=new_title,
            metadata=parsed.metadata or {},
            tags=parsed.tags,
            wiki_links=parsed.wiki_links,
            entities=parsed.entities,
        )

        # Process wiki links
        process_wiki_links(conn, note_obj)

        # Resolve incoming wiki links from other notes that link to this one
        _resolve_incoming_wiki_links(conn, note_obj)

        # Return updated note
        tags = get_tags_for_note(conn, new_note_id)
        metadata = {}
        if parsed.metadata:
            metadata = parsed.metadata

        return NoteDetail(
            note_id=new_note_id,
            title=new_title,
            path=str(updated.path),
            tags=tags,
            content=new_content,
            metadata=metadata,
            created_at=note_record.get("created_at"),
            updated_at=datetime.now().isoformat(),
        )
    finally:
        conn.close()


@router.delete("/{note_id}")
async def delete_note(note_id: str) -> dict:
    """Delete a note from the vault and database."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id, delete_note_by_id as db_delete_note

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_record = get_note_by_id(conn, note_id)
        if not note_record:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        # Delete file from disk
        note_path = note_record.get("path", "")
        if note_path:
            file_path = Path(note_path)
            if file_path.exists():
                file_path.unlink()

        # Delete from database
        db_delete_note(conn, note_id)

        return {"message": "Note deleted", "note_id": note_id}
    finally:
        conn.close()


# ─── Version history / Diff ──────────────────────────────────────────────

@router.get("/{note_id}/versions", response_model=NoteVersionsResponse)
async def get_versions(note_id: str) -> NoteVersionsResponse:
    """List all saved versions of a note."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_record = get_note_by_id(conn, note_id)
        if not note_record:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        note_path = note_record.get("path", "")
        if not note_path:
            return NoteVersionsResponse(note_id=note_id, versions=[])

        file_path = Path(note_path)
        versions_dir = _get_versions_dir(file_path)

        versions: list[NoteVersion] = []
        meta_files = sorted(versions_dir.glob("v*.meta"), key=lambda p: p.name)
        for meta_file in meta_files:
            try:
                meta_content = meta_file.read_text(encoding="utf-8")
                meta: dict[str, str] = {}
                for line in meta_content.strip().split("\n"):
                    if ": " in line:
                        k, v = line.split(": ", 1)
                        meta[k.strip()] = v.strip()
                versions.append(NoteVersion(
                    version=int(meta.get("version", "0")),
                    content_hash=meta.get("content_hash", ""),
                    saved_at=meta.get("saved_at", ""),
                    content_length=int(meta.get("content_length", "0")),
                ))
            except (ValueError, OSError):
                continue

        return NoteVersionsResponse(note_id=note_id, versions=versions)
    finally:
        conn.close()


@router.get("/{note_id}/diff", response_model=DiffResponse)
async def get_diff(
    note_id: str,
    old_version: int = Query(..., ge=1),
    new_version: int = Query(..., ge=1),
) -> DiffResponse:
    """Compare two versions of a note and return a unified diff."""
    from gunita.config import settings
    from bfai.db import connect, ensure_schema, get_note_by_id

    conn = connect(settings.database_path)
    try:
        ensure_schema(conn)

        note_record = get_note_by_id(conn, note_id)
        if not note_record:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found")

        note_path = note_record.get("path", "")
        if not note_path:
            raise HTTPException(status_code=500, detail="Note has no file path")

        file_path = Path(note_path)
        versions_dir = _get_versions_dir(file_path)

        old_file = versions_dir / f"v{old_version}.md"
        new_file = versions_dir / f"v{new_version}.md"

        if not old_file.exists():
            raise HTTPException(status_code=404, detail=f"Version {old_version} not found")
        if not new_file.exists():
            raise HTTPException(status_code=404, detail=f"Version {new_version} not found")

        old_content = old_file.read_text(encoding="utf-8")
        new_content = new_file.read_text(encoding="utf-8")

        # Generate unified diff
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_result = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"v{old_version}",
            tofile=f"v{new_version}",
            lineterm="",
        ))

        # Parse diff into structured lines
        diff_lines: list[DiffLine] = []
        old_line = 0
        new_line = 0
        for line in diff_result:
            if line.startswith("@@"):
                # Skip hunk headers
                continue
            elif line.startswith("-"):
                old_line += 1
                diff_lines.append(DiffLine(
                    type="removed",
                    content=line[1:] if line.startswith("-") else line,
                    old_line=old_line,
                    new_line=None,
                ))
            elif line.startswith("+"):
                new_line += 1
                diff_lines.append(DiffLine(
                    type="added",
                    content=line[1:] if line.startswith("+") else line,
                    old_line=None,
                    new_line=new_line,
                ))
            else:
                old_line += 1
                new_line += 1
                diff_lines.append(DiffLine(
                    type="unchanged",
                    content=line[1:] if line.startswith(" ") else line,
                    old_line=old_line,
                    new_line=new_line,
                ))

        return DiffResponse(
            old_version=old_version,
            new_version=new_version,
            lines=diff_lines,
        )
    finally:
        conn.close()