"""Vault filesystem endpoints.

GET  /api/vault/            — Directory tree of the vault
GET  /api/vault/read        — Read a specific file's content
GET  /api/vault/vaults      — List all available vaults
GET  /api/vault/image       — Serve an image file from the vault
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class TreeNode(BaseModel):
    """A single node in the vault file tree."""
    name: str
    path: str  # absolute path
    type: str  # "file" | "directory"
    children: list[TreeNode] = []
    is_note: bool = False  # True for .md files


class FileContent(BaseModel):
    """Content of a vault file."""
    path: str
    name: str
    content: str


class VaultInfo(BaseModel):
    """Information about a vault."""
    name: str
    path: str
    is_primary: bool = False


class VaultListResponse(BaseModel):
    """List of available vaults."""
    vaults: list[VaultInfo]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/", response_model=TreeNode)
async def get_tree() -> TreeNode:
    """Return the vault directory tree."""
    from gunita.config import settings

    vault_root = settings.vault_path
    if not vault_root.exists():
        raise HTTPException(status_code=404, detail="Vault not found")

    return _build_tree(vault_root)


def _build_tree(path: Path) -> TreeNode:
    """Recursively build a tree node from a directory path."""
    children: list[TreeNode] = []

    if path.is_dir():
        for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if entry.name.startswith("."):
                continue
            if entry.is_dir() or entry.suffix.lower() in (".md",):
                children.append(_build_tree(entry))

    return TreeNode(
        name=path.name,
        path=str(path),
        type="directory" if path.is_dir() else "file",
        children=children,
        is_note=path.suffix.lower() == ".md",
    )


@router.get("/read", response_model=FileContent)
async def read_file(
    path: str = Query(..., description="Absolute file path to read"),
) -> FileContent:
    """Read the contents of a vault file."""
    from gunita.config import settings

    file_path = Path(path)

    # Security: ensure the file is within any of the allowed vaults
    is_allowed = False
    for vault_path in settings.all_vault_paths:
        try:
            file_path.resolve().is_relative_to(vault_path.resolve())
            is_allowed = True
            break
        except (ValueError, OSError):
            continue

    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: path outside vault")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = "(binary file — cannot display)"

    return FileContent(
        path=str(file_path),
        name=file_path.name,
        content=content,
    )


# ─── Cross-vault support ────────────────────────────────────────────────

@router.get("/vaults", response_model=VaultListResponse)
async def list_vaults() -> VaultListResponse:
    """List all available vaults (primary + extra vaults)."""
    from gunita.config import settings

    vaults: list[VaultInfo] = []
    for i, vp in enumerate(settings.all_vault_paths):
        vaults.append(VaultInfo(
            name=vp.name,
            path=str(vp),
            is_primary=(i == 0),
        ))
    return VaultListResponse(vaults=vaults)


@router.get("/image")
async def serve_image(
    path: str = Query(..., description="Absolute path to image file"),
) -> FileResponse:
    """Serve an image file from the vault.

    Supports common image formats: png, jpg, jpeg, gif, svg, webp.
    """
    from gunita.config import settings

    file_path = Path(path)

    # Security: ensure the file is within any vault
    is_allowed = False
    for vault_path in settings.all_vault_paths:
        try:
            if file_path.resolve().is_relative_to(vault_path.resolve()):
                is_allowed = True
                break
        except (ValueError, OSError):
            continue

    if not is_allowed:
        raise HTTPException(status_code=403, detail="Access denied: path outside vault")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    # Check it's an image file
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}
    if file_path.suffix.lower() not in image_exts:
        raise HTTPException(status_code=400, detail="Not an image file")

    # Determine media type
    ext = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".ico": "image/x-icon",
    }

    return FileResponse(
        str(file_path),
        media_type=media_types.get(ext, "application/octet-stream"),
    )