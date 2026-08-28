#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Read/write Recoil PARAM_MOTOR_PHASE_ORDER (CAN 0x10C) and store flash.

This is the live Recoil object-dictionary value, not the firmware
``#define MOTOR_PHASE_ORDER`` in Recoil Core/Inc/motor_controller_conf.h.

Lab (2026-08-27): flipping this CAN value from +1 to -1 did **not** reverse
the first electrical-offset spin. Berkeley docs want that first spin CCW,
then CW. If it is CW first, do one of:

  1. Swap any two of the three motor PHASE wires (U/V/W, not CAN), or
  2. Change MOTOR_PHASE_ORDER to -1 in Recoil firmware and reflash.

Do not stack a CAN -1 with a wire swap. Leave this parameter at +1 unless
you are following a firmware reflash.

    python3 ./scripts/set_phase_order.py --channel can1 --id 3 --order 1

See docs/BRINGUP.md.
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Flip Recoil phase order and store to flash.")
    parser.add_argument("-c", "--channel", "--port", dest="channel", required=True)
    parser.add_argument("-i", "--id", dest="device_id", type=int, required=True)
    parser.add_argument(
        "--order",
        type=int,
        choices=(-1, 1),
        default=None,
        help="Set this value instead of flipping the current one",
    )
    args = parser.parse_args(argv)

    bus = recoil.Bus(channel=args.channel, bitrate=1_000_000)
    try:
        if not bus.ping(args.device_id):
            print(f"Motor is offline ({args.channel} id {args.device_id})", file=sys.stderr)
            return 1
        current = bus.read_motor_phase_order(args.device_id)
        if args.order is None:
            if current is None:
                print("Could not read phase_order.", file=sys.stderr)
                return 1
            new = -1 if current >= 0 else 1
        else:
            new = args.order
        print(f"phase_order {current} -> {new}")
        bus.write_motor_phase_order(args.device_id, new)
        time.sleep(0.05)
        bus.store_settings_to_flash(args.device_id)
        time.sleep(0.2)
        print(f"stored. read-back: {bus.read_motor_phase_order(args.device_id)}")
        print(
            "Stored CAN PARAM_MOTOR_PHASE_ORDER. This write does not reverse "
            "the first electrical-offset spin; see docs/BRINGUP.md."
        )
        return 0
    finally:
        try:
            bus.stop()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())
