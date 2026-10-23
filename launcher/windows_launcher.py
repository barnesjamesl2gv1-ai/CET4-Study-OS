"""Single-instance loopback launcher for the packaged Windows application."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from backend.db import data_dir


def choose_socket(preferred: int = 8765) -> socket.socket:
    for port in (preferred, 0):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", port))
            listener.listen()
            return listener
        except OSError:
            listener.close()
    raise OSError("无法绑定本机端口")


def open_edge(url: str) -> None:
    candidates = [Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
                  Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe"]
    executable = next((path for path in candidates if path.is_file()), None)
    if executable:
        subprocess.Popen([str(executable), url])
    else:
        raise RuntimeError("找不到 Microsoft Edge，请安装后重试")


def main() -> None:
    if "--self-test" in sys.argv:
        import tempfile
        from backend.db import initialize
        from backend.app import app  # noqa: F401 - verify packaged imports

        with tempfile.TemporaryDirectory() as scratch:
            initialize(Path(scratch) / "test.sqlite3")
        bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        if not (bundle_root / "frontend" / "dist" / "index.html").is_file():
            raise RuntimeError("前端资源未打包")
        print("CET4StudyOS bundle self-test passed")
        return
    if sys.platform != "win32":
        raise RuntimeError("此启动器仅用于 Windows")
    import msvcrt
    import uvicorn

    root = data_dir()
    lock_file = (root / "launcher.lock").open("a+b")
    lock_file.write(b"0")
    lock_file.flush()
    lock_file.seek(0)
    try:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        state_path = root / "server.json"
        for _ in range(30):
            try:
                port = json.loads(state_path.read_text(encoding="utf-8"))["port"]
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                    if response.status == 200:
                        open_edge(f"http://127.0.0.1:{port}/")
                        return
            except (OSError, ValueError, KeyError):
                time.sleep(0.2)
        raise RuntimeError("已有实例运行，但无法连接其服务")
    listener = choose_socket()
    port = listener.getsockname()[1]
    (root / "server.json").write_text(json.dumps({"port": port}), encoding="utf-8")
    from backend.app import app
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    try:
        import asyncio

        async def run():
            async def open_when_ready():
                for _ in range(100):
                    if server.started:
                        open_edge(f"http://127.0.0.1:{port}/")
                        return
                    await asyncio.sleep(0.1)
                raise RuntimeError("本地服务启动超时")

            task = asyncio.create_task(open_when_ready())
            await server.serve(sockets=[listener])
            await task

        asyncio.run(run())
    finally:
        listener.close()
        (root / "server.json").unlink(missing_ok=True)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        lock_file.close()


if __name__ == "__main__":
    main()
