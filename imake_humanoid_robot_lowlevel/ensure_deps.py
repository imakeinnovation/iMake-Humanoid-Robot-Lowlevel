# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Runtime dependency checks with operator-facing install hints."""

from __future__ import annotations

CAN_INSTALL_HINT = """No module named 'can' (the python-can package).

Ubuntu 24 / Python 3.12 blocks `pip install` on system Python
(externally-managed-environment). Do not use --break-system-packages.

On the robot PC, install the Debian package, then retry with the same python3:

  sudo apt install python3-can python3-venv python3-full
  python3 -c "import can; print(can.__file__)"
  export PYTHONPATH="$PWD"
  python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can2 --id 1

If apt cannot provide python3-can, use a venv (then call that python, not system python3):

  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install python-can
  export PYTHONPATH="$PWD"
  python ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can2 --id 1
"""


def require_python_can() -> None:
    try:
        import can  # noqa: F401
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", None)
        if missing not in (None, "can"):
            raise
        raise ModuleNotFoundError(CAN_INSTALL_HINT) from exc
