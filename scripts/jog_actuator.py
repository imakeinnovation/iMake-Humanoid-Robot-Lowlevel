#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Slow visible jog around the actuator's current angle. Ctrl+C -> IDLE."""

from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import imake_humanoid_robot_lowlevel.recoil as recoil


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Oscillate one Recoil motor around its current position.")
    parser.add_argument("-c", "--channel", "--port", dest="channel", default="can1")
    parser.add_argument("-i", "--id", dest="device_id", type=int, default=3)
    parser.add_argument("--amplitude", type=float, default=0.5, help="radians, each side of current pose")
    parser.add_argument("--frequency", type=float, default=0.2, help="Hz (slow enough to see)")
    parser.add_argument("--torque", type=float, default=4.0, help="Nm torque limit")
    args = parser.parse_args(argv)

    bus = recoil.Bus(channel=args.channel, bitrate=1_000_000)
    try:
        if not bus.ping(args.device_id):
            print(f"Motor is offline ({args.channel} id {args.device_id})", file=sys.stderr)
            return 1

        center = bus.read_position_measured(args.device_id)
        if center is None:
            print("Could not read encoder position.", file=sys.stderr)
            return 1

        print(
            f"Jog {args.channel} id {args.device_id} around {center:.3f} rad "
            f"(±{args.amplitude} rad at {args.frequency} Hz). Ctrl+C to stop."
        )

        bus.write_position_kp(args.device_id, 20.0)
        bus.write_position_kd(args.device_id, 2.0)
        bus.write_torque_limit(args.device_id, args.torque)
        bus.set_mode(args.device_id, recoil.Mode.POSITION)
        bus.feed(args.device_id)

        t0 = time.time()
        last_print = 0.0
        while True:
            t = time.time() - t0
            target = center + args.amplitude * math.sin(2 * math.pi * args.frequency * t)
            measured_position, measured_velocity = bus.write_read_pdo_2(args.device_id, target, 0.0)
            now = time.time()
            if now - last_print >= 0.25:
                vel = measured_velocity if measured_velocity is not None else float("nan")
                pos = measured_position if measured_position is not None else float("nan")
                print(f"target {target:7.3f}  meas {pos:7.3f}  vel {vel:7.3f}")
                last_print = now
            time.sleep(0.005)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        try:
            bus.set_mode(args.device_id, recoil.Mode.IDLE)
        except Exception:  # noqa: BLE001
            pass
        try:
            bus.stop()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
