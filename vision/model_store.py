"""Download MediaPipe task files when missing. Never fabricates model bytes."""

from __future__ import annotations

import urllib.request
from pathlib import Path

from services.logger import log


def ensure_model(path: Path, url: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 1024:
        return True
    log.info("Downloading model %s ...", path.name)

    def progress(block: int, block_size: int, total: int) -> None:
        if total > 0:
            pct = min(100, block * block_size * 100 // total)
            print(f"\r[AURA] Downloading {path.name}... {pct:3d}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, path, progress)
        print()
        if not path.exists() or path.stat().st_size < 1024:
            log.error("Downloaded file looks incomplete: %s", path)
            if path.exists():
                path.unlink()
            return False
        log.info("Model ready: %s", path.name)
        return True
    except Exception as error:
        log.error("Model download failed: %s", error)
        if path.exists():
            path.unlink()
        return False
