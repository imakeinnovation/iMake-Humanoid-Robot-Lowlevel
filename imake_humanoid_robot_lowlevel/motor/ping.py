#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Ping one actuator. Matches the robot-computer invocation:

    python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --port can2 --id 1
"""

from pathlib import Path
import sys

# imake_humanoid_robot_lowlevel/motor/ping.py -> low-level repo root
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from imake_humanoid_robot_lowlevel.can_iface import run_ping  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_ping())
