# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Locate the low-level repo root so scripts work without pip install -e ."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_lowlevel_on_path() -> Path:
    here = Path(__file__).resolve()
    root = None
    for parent in here.parents:
        if (parent / "imake_humanoid_robot_lowlevel" / "recoil").is_dir():
            root = parent
            break
    if root is None:
        root = here.parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root
