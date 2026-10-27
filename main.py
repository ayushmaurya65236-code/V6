"""AURA LINK V6 entry point."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.app_controller import AppController  # noqa: E402
from services.logger import log  # noqa: E402


def main() -> int:
    app = AppController()
    try:
        app.run()
    except KeyboardInterrupt:
        log.info("Interrupted")
        app.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
