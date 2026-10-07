#!/usr/bin/env python3
"""Run independent acquired-source scans sequentially without shell interpolation."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    codes = []
    for source in ("criteo_uplift", "criteo_attribution", "obd_men"):
        codes.append(subprocess.run([sys.executable, str(root / "tools/admit_source.py"), source], cwd=root, check=False).returncode)
    return 0 if all(code == 0 for code in codes) else 2


if __name__ == "__main__":
    raise SystemExit(main())
