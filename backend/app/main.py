from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from . import crud, schemas, sync
from .database import Base, SessionLocal, engine, get_db
from .events import hub
from .paths import frontend_dist


def _migrate_sqlite() -> None:
    statements = [
        "ALTER TABLE tasks ADD COLUMN source VARCHAR(16) NOT NULL DEFAULT 'manual'",
        "ALTER TABLE tasks ADD COLUMN external_key VARCHAR(240)",
        "ALTER TABLE tasks ADD COLUMN live BOOLEAN NOT NULL DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN last_seen_at DATETIME",
    ]
    with engine.begin() as conn:
        for statement in statements:
            try:
                conn.execute(text(statement))
            except Exception:
                pass
        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_tasks_external_key "
                    "ON tasks(external_key)"
                )
            )
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    import asyncio

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    db = SessionLocal()
    try:
        crud.seed_board(db)
    finally:
        db.close()

    hub.bind_loop(asyncio.get_running_loop())
    sync.start_watcher(interval=2.0)
    try:
        sync.sync_once(force_broadcast=True)
    except Exception:
        pass
    yield
    sync.stop_watcher()


app = FastAPI(title="Agent Task Tracker", version="1.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8787",
        "http://localhost:8787",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sync/status")
def read_sync_status() -> dict:
    return sync.sync_status()


@app.post("/api/sync/now")
def sync_now() -> dict:
    """Rescan local agent directories (read-only). Does not write agent files."""
    return sync.sync_once(force_broadcast=True)


@app.get("/api/events")
async def board_events() -> EventSourceResponse:
    return EventSourceResponse(hub.stream())


@app.get("/api/board", response_model=schemas.BoardOut)
def read_board(db: Session = Depends(get_db)) -> schemas.BoardOut:
    return crud.get_board(db)


@app.get("/api/projects/hidden", response_model=schemas.HiddenProjectsOut)
def read_hidden_projects(db: Session = Depends(get_db)) -> schemas.HiddenProjectsOut:
    return schemas.HiddenProjectsOut(paths=crud.list_hidden_projects(db))


@app.post("/api/projects/hide", response_model=schemas.HiddenProjectsOut)
def hide_project(
    payload: schemas.HiddenProjectIn, db: Session = Depends(get_db)
) -> schemas.HiddenProjectsOut:
    """Hide a project from the board only. Does not touch agent files or synced rows."""
    paths = crud.hide_project(db, payload.path)
    hub.publish({"type": "board", "reason": "project_hidden"})
    return schemas.HiddenProjectsOut(paths=paths)


@app.post("/api/projects/unhide", response_model=schemas.HiddenProjectsOut)
def unhide_project(
    payload: schemas.HiddenProjectIn, db: Session = Depends(get_db)
) -> schemas.HiddenProjectsOut:
    """Restore a previously hidden project on the board."""
    paths = crud.unhide_project(db, payload.path)
    hub.publish({"type": "board", "reason": "project_unhidden"})
    return schemas.HiddenProjectsOut(paths=paths)


STATIC_DIR = frontend_dist()


def mount_frontend() -> None:
    if not STATIC_DIR.exists():
        return
    assets = STATIC_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json", "redoc"}:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")


mount_frontend()
