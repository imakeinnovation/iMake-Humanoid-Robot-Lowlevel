#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Recoil electrical-offset calibration for iMAKE (one actuator).

This is the same Recoil Mode.CALIBRATION sequence as
scripts/motor/calibrate_electrical_offset.py. The shaft WILL SPIN
for about 20 seconds. Do not run Humanoid() or calibrate_joints.py
from this script.

The motor you already pinged as online:

    python3 ./scripts/calibrate_electrical_offset.py --channel can1 --id 3

Expected motion (Berkeley flashing docs): CCW one turn, then CW.
If the first turn is CW, CAN phase_order will not fix it — see docs/BRINGUP.md.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import imake_humanoid_robot_lowlevel.recoil as recoil


CALIBRATION_SECONDS = 20


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Calibrate Recoil electrical offset on one iMAKE actuator. The motor will spin."
    )
    parser.add_argument(
        "-c", "--channel", "--port",
        dest="channel",
        required=True,
        help="SocketCAN interface, e.g. can1",
    )
    parser.add_argument(
        "-i", "--id",
        dest="device_id",
        type=int,
        required=True,
        help="Recoil CAN id, e.g. 3",
    )
    args = parser.parse_args(argv)

    print(
        f"iMAKE electrical offset: {args.channel} id {args.device_id}\n"
        f"The shaft will spin for {CALIBRATION_SECONDS}s. Do not press Ctrl+C.\n"
        "Keep the joint free to rotate."
    )

    bus = recoil.Bus(channel=args.channel, bitrate=1_000_000)
    try:
        if not bus.ping(args.device_id):
            print(
                f"Motor is offline ({args.channel} id {args.device_id}). "
                "Ping must succeed before electrical offset.",
                file=sys.stderr,
            )
            return 1
        print("Motor is online. Starting Recoil calibration mode.")
        bus.set_mode(args.device_id, recoil.Mode.CALIBRATION)
        time.sleep(CALIBRATION_SECONDS)
        print("Wait finished. Electrical-offset command sequence complete.")
        return 0
    finally:
        try:
            bus.stop()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
