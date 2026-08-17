"""Verify that the built CADiPy package exposes the intended release surface."""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    wheels = sorted((ROOT / "dist").glob("cadipy-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one CADiPy wheel, found {len(wheels)}")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = set(archive.namelist())
        required = {
            "cadipy/__init__.py",
            "cadipy/py.typed",
            "cadipy/cli.py",
            "cadipy/operations/registry.py",
            "cadipy/backends/executor.py",
        }
        missing = sorted(required - names)
        if missing:
            raise SystemExit(f"missing required package files: {missing}")
        top_level = {name.split("/", 1)[0] for name in names if "/" in name}
        allowed = {"cadipy"} | {name for name in top_level if name.endswith(".dist-info")}
        unexpected = sorted(top_level - allowed)
        if unexpected:
            raise SystemExit(f"unexpected package content: {unexpected}")
    print(f"verified {wheels[0].name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
