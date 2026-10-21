# SPDX-License-Identifier: Apache-2.0
"""Serve the built web client from inside the package.

The release build drops ``web/dist`` into ``pineda_web/webroot/`` so a single
``pip install pineda-web`` (or the Docker image, or the .deb) ships the whole
app — no separate frontend build for the user. In a source checkout the folder
is absent and the server simply runs API-only; run ``pnpm --filter
@pinedaview/client dev`` for the UI during development.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def webroot_dir() -> Path:
    """The bundled client directory (may not exist in a source checkout)."""
    return Path(__file__).parent / "webroot"


def has_web() -> bool:
    return (webroot_dir() / "index.html").is_file()


def mount_web(app: FastAPI) -> None:
    """Serve bundled assets and fall back to ``index.html`` for client routes.

    A no-op when the client hasn't been bundled. Must be called after every
    ``/api`` route is registered so those keep priority.
    """
    # Resolved, since each candidate is: through a symlinked path (/opt on
    # primary-server) every top-level file, sw.js included, fell back to index.html.
    root = webroot_dir().resolve()
    if not has_web():
        logger.info("no bundled web client (%s) — running API-only", root)
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="not found")
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)
        # Revalidate every load: the hashed /assets are immutable, but a cached
        # index.html keeps a kiosk on the old build after a deploy.
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})

    logger.info("serving bundled web client from %s", root)
