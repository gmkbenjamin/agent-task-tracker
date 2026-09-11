from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.paths import is_frozen  # noqa: E402

HOST = "127.0.0.1"
PORT = 8787


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return
            except OSError:
                time.sleep(0.15)
    raise RuntimeError(f"Server did not start on http://{host}:{port}")


def run_server(host: str, port: int) -> None:
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="warning" if is_frozen() else "info",
        reload=False,
    )


def open_desktop(url: str) -> None:
    import webview

    webview.create_window(
        "Agent Task Tracker",
        url,
        width=1440,
        height=920,
        min_size=(960, 640),
        background_color="#e8eef2",
    )
    webview.start()


def open_browser(url: str) -> None:
    import webbrowser

    webbrowser.open(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Agent Task Tracker")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--browser",
        action="store_true",
        help="Open the system browser instead of a native window",
    )
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    server = threading.Thread(
        target=run_server, args=(args.host, args.port), daemon=True
    )
    server.start()
    wait_for_server(args.host, args.port)

    if args.browser:
        open_browser(url)
        server.join()
    else:
        try:
            open_desktop(url)
        except ImportError:
            print("pywebview is unavailable; falling back to the system browser.")
            open_browser(url)
            server.join()


if __name__ == "__main__":
    main()
