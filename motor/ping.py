#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Ping one actuator from the low-level repo root or from source/."""

from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from imake_humanoid_robot_lowlevel.can_iface import run_ping  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_ping())
