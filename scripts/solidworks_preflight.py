"""Launch and close an owned hidden SOLIDWORKS instance for CI preflight."""

from __future__ import annotations

import json
import platform
import sys
from contextlib import suppress

from cadipy.backends.solidworks import PythonComSolidWorksExecutor

EXPECTED_REVISION = "34.3.2"


def main() -> int:
    if platform.system() != "Windows" or sys.version_info[:2] != (3, 12):
        print(
            json.dumps(
                {
                    "ok": False,
                    "platform": platform.system(),
                    "python": platform.python_version(),
                    "error": "strict SOLIDWORKS preflight requires Windows and Python 3.12",
                }
            )
        )
        return 1

    executor = PythonComSolidWorksExecutor()
    try:
        info = executor.launch(visible=False)
        report = {
            "ok": info.revision == EXPECTED_REVISION and info.visible is False,
            "platform": platform.system(),
            "python": platform.python_version(),
            "product": info.product,
            "revision": info.revision,
            "executor": info.executor,
            "connection_mode": info.connection_mode,
            "owned": info.owned,
            "visible": info.visible,
        }
        print(json.dumps(report, sort_keys=True))
        return 0 if report["ok"] else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "platform": platform.system(),
                    "python": platform.python_version(),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        )
        return 1
    finally:
        with suppress(Exception):
            executor.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
