"""Confined SPA serving: never serve files outside the built frontend."""
from pathlib import Path, PurePosixPath
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

def resolve_frontend_file(root: Path, requested: str) -> Path:
    # ASGI already URL-decodes paths. Reject Windows separators too.
    if chr(0) in requested or chr(92) in requested:
        raise HTTPException(status_code=404, detail='Not found')
    parts = PurePosixPath(requested).parts
    if PurePosixPath(requested).is_absolute() or any(
        part == '..' or part.startswith('.') for part in parts
    ):
        raise HTTPException(status_code=404, detail='Not found')
    try:
        base = root.resolve(strict=True)
        candidate = (base / requested).resolve()
        candidate.relative_to(base)
    except (ValueError, OSError, RuntimeError):
        raise HTTPException(status_code=404, detail='Not found') from None
    return candidate

def mount_frontend(app: FastAPI, root: Path) -> None:
    root = Path(root)
    if not root.is_dir():
        return
    assets = resolve_frontend_file(root, 'assets')
    if assets.is_dir():
        app.mount('/assets', StaticFiles(directory=assets, follow_symlink=False), name='assets')

    @app.get('/')
    def index() -> FileResponse:
        candidate = resolve_frontend_file(root, 'index.html')
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail='Not found')
        return FileResponse(candidate)

    @app.get('/{full_path:path}')
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == 'api' or full_path.startswith('api/') or full_path in {'docs', 'openapi.json', 'redoc'}:
            raise HTTPException(status_code=404, detail='Not found')
        candidate = resolve_frontend_file(root, full_path)
        if candidate.is_file():
            return FileResponse(candidate)
        return index()
