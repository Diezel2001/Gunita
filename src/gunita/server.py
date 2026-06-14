"""FastAPI application factory.

Creates and configures the FastAPI app, mounts static files,
includes all API route modules, and provides WebSocket + auth middleware.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, Security
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import APIKeyHeader
from starlette.types import Scope, Receive, Send

from gunita.api.router import api_router
from gunita.config import settings

logger = logging.getLogger("gunita.server")

HERE = Path(__file__).parent

# ─── WebSocket connection manager ─────────────────────────────────────────

class ConnectionManager:
    """Manages active WebSocket connections for live updates."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.debug("WebSocket connected (total: %d)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        logger.debug("WebSocket disconnected (total: %d)", len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients."""
        text = json.dumps(message)
        disconnected: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(text)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


ws_manager = ConnectionManager()


# ─── API key verification ────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str | None:
    """Verify the API key if one is configured.

    Returns the key if valid, or None if no key is configured (open access).
    Raises HTTPException if a key is required but missing/invalid.
    """
    if not settings.api_key:
        return None  # No auth required
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide it via X-API-Key header.",
        )
    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key.")
    return api_key


# ─── App factory ─────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and return a configured FastAPI application instance."""
    app = FastAPI(
        title="Gunita",
        description="Web UI and REST API for the BFAI memory system",
        version="0.2.0",
        docs_url="/docs" if settings.reload else None,
        redoc_url=None,
    )

    # ── API routes ──────────────────────────────────────────────
    app.include_router(api_router, prefix="/api")

    # ── Static files (CSS, JS) with no-cache headers ────────────
    static_dir = HERE / "static"
    if static_dir.exists():
        class NoCacheStaticFiles(StaticFiles):
            """StaticFiles that sends no-cache headers for JS files."""
            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                async def send_wrapper(message):
                    if message["type"] == "http.response.start":
                        original_headers = message.get("headers", [])
                        # Add Cache-Control: no-cache for JS files
                        if scope["path"].endswith(".js"):
                            message["headers"] = [
                                h for h in original_headers
                                if h[0].lower() != b"cache-control"
                            ] + [(b"cache-control", b"no-cache, no-store, must-revalidate")]
                    await send(message)
                await super().__call__(scope, receive, send_wrapper)

        app.mount("/static", NoCacheStaticFiles(directory=str(static_dir)), name="static")

    # ── SPA fallback: serve index.html for all non-API routes ───
    index_html_path = HERE / "templates" / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all route: serve the SPA for any unmatched path."""
        from fastapi.responses import FileResponse

        if index_html_path.exists():
            return FileResponse(str(index_html_path), media_type="text/html")
        return {"error": "SPA index.html not found"}

    # ── WebSocket endpoint for live updates ──────────────────────
    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        """WebSocket endpoint for real-time graph and search updates."""
        await ws_manager.connect(ws)
        try:
            while True:
                data = await ws.receive_text()
                msg = json.loads(data) if data else {}
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

                elif msg_type == "subscribe_graph":
                    # Client wants to be notified of graph changes
                    await ws.send_text(json.dumps({
                        "type": "subscribed",
                        "channel": "graph",
                    }))

                elif msg_type == "request_refresh":
                    # Client requests a full data refresh
                    await ws.send_text(json.dumps({
                        "type": "refresh_needed",
                        "channel": msg.get("channel", "graph"),
                    }))

        except WebSocketDisconnect:
            ws_manager.disconnect(ws)
        except Exception as exc:
            logger.debug("WebSocket error: %s", exc)
            ws_manager.disconnect(ws)

    # ── Lifespan: log startup info ──────────────────────────────
    @app.on_event("startup")
    async def startup() -> None:
        logger.info(
            "Gunita v0.2.0 starting — http://%s:%d",
            settings.host,
            settings.port,
        )
        logger.info("Vault path: %s", settings.vault_path)
        logger.info("Database  : %s", settings.database_path)
        if settings.api_key:
            logger.info("API key   : configured (authentication enabled)")
        else:
            logger.info("API key   : not configured (open access)")
        if settings.extra_vaults:
            logger.info("Extra vaults: %s", settings.extra_vaults)

    return app


# Module-level app instance for uvicorn discovery
app = create_app()