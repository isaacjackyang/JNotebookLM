from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"


def _is_running_inside_repo_venv() -> bool:
    try:
        return Path(sys.executable).resolve() == VENV_PYTHON.resolve()
    except FileNotFoundError:
        return False


def _reexec_into_repo_venv() -> "subprocess.CompletedProcess[int]":
    command = [str(VENV_PYTHON), str(ROOT_DIR / "run.py"), *sys.argv[1:]]
    return subprocess.run(command, check=False)


def _should_auto_open() -> bool:
    value = os.getenv("JNOTEBOOKLM_AUTO_OPEN", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _build_url() -> str:
    host = os.getenv("JNOTEBOOKLM_HOST", "127.0.0.1")
    port = os.getenv("JNOTEBOOKLM_PORT", "8000")
    return f"http://{host}:{port}/"


def _open_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    break
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.5)
    else:
        return

    try:
        os.startfile(url)  # type: ignore[attr-defined]
    except AttributeError:
        webbrowser.open(url, new=2)


def main() -> int:
    if not _is_running_inside_repo_venv() and VENV_PYTHON.exists():
        return _reexec_into_repo_venv().returncode

    try:
        from app.main import run
    except ModuleNotFoundError as exc:
        missing = exc.name or "dependency"
        print(
            (
                f"Missing Python dependency: {missing}\n\n"
                "Use the project virtual environment:\n"
                r"  .\.venv\Scripts\python.exe run.py"
                "\n\n"
                "Or install dependencies into the current interpreter:\n"
                "  pip install -r requirements.txt"
            ),
            file=sys.stderr,
        )
        return 1

    if _should_auto_open():
        url = _build_url()
        thread = threading.Thread(target=_open_when_ready, args=(url,), daemon=True)
        thread.start()

    run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
