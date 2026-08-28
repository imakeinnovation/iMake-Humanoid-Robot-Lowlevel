#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Same move_actuator as scripts/motor/move_actuator.py, next to ping.py."""

from pathlib import Path
import runpy
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SCRIPT = _ROOT / "scripts" / "motor" / "move_actuator.py"
runpy.run_path(str(_SCRIPT), run_name="__main__")
