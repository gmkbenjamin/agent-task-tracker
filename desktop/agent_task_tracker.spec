# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Agent Task Tracker (run via scripts/build-app.sh)."""

from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"

if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit(
        f"Missing built UI at {FRONTEND_DIST}. Run: cd frontend && npm run build"
    )

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "app",
    "app.main",
    "app.database",
    "app.crud",
    "app.schemas",
    "app.sync",
    "app.events",
    "app.paths",
    "app.models",
    "app.agents",
    "app.agents.claude",
    "app.agents.codex",
    "app.agents.cursor",
    "app.agents.grok",
    "app.agents.grok_bot",
    "app.agents.types",
]
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("sse_starlette")

binaries = []
for package in ("webview", "fastapi", "pydantic", "sqlalchemy"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

block_cipher = None

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Agent Task Tracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Agent Task Tracker",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Agent Task Tracker.app",
        icon=None,
        bundle_identifier="com.local.agent-task-tracker",
        info_plist={
            "CFBundleName": "Agent Task Tracker",
            "CFBundleDisplayName": "Agent Task Tracker",
            "CFBundleShortVersionString": "1.3.0",
            "CFBundleVersion": "1.3.0",
            "NSHighResolutionCapable": True,
            "LSPrincipalClass": "NSApplication",
        },
    )
