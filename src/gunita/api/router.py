"""Main API router — aggregates all endpoint modules.

Provides:
  /api/graph      — Knowledge graph data (nodes + edges)
  /api/notes      — Note CRUD and detail retrieval
  /api/search     — Keyword / semantic / hybrid search
  /api/vault      — Vault filesystem tree + file contents
  /api/stats      — Vault statistics and reindex trigger
"""

from fastapi import APIRouter

from gunita.api.graph import router as graph_router
from gunita.api.notes import router as notes_router
from gunita.api.search import router as search_router
from gunita.api.vault import router as vault_router
from gunita.api.stats import router as stats_router

api_router = APIRouter()

api_router.include_router(graph_router, prefix="/graph", tags=["graph"])
api_router.include_router(notes_router, prefix="/notes", tags=["notes"])
api_router.include_router(search_router, prefix="/search", tags=["search"])
api_router.include_router(vault_router, prefix="/vault", tags=["vault"])
api_router.include_router(stats_router, prefix="/stats", tags=["stats"])