#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Ping biped IDs on every SocketCAN bus. No motion, no IMU, no gamepad."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from imake_humanoid_robot_lowlevel.can_iface import socketcan_status
import imake_humanoid_robot_lowlevel.recoil as recoil

BUSES = ("can0", "can1", "can2", "can3")
IDS = (1, 2, 3, 4, 5, 6, 7, 8, 11, 12, 13, 14)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ping Recoil ids on can0–can3.")
    parser.add_argument("--timeout", type=float, default=0.05)
    args = parser.parse_args(argv)

    print(f"{'bus':<6} {'id':>3}  result")
    print("-" * 28)
    online = 0
    tried = 0

    for channel in BUSES:
        state = socketcan_status(channel)
        if state != "up":
            print(f"{channel:<6} {'—':>3}  skip ({state})")
            continue
        bus = None
        try:
            bus = recoil.Bus(channel=channel, bitrate=1_000_000)
            if hasattr(bus, "_note_error_frame"):
                bus._note_error_frame = lambda msg: None  # type: ignore[method-assign]
            for device_id in IDS:
                tried += 1
                try:
                    ok = bool(bus.ping(device_id, timeout=args.timeout))
                except Exception as exc:  # noqa: BLE001
                    print(f"{channel:<6} {device_id:3d}  ERROR {type(exc).__name__}: {exc}")
                    continue
                label = "online" if ok else "offline"
                if ok:
                    online += 1
                print(f"{channel:<6} {device_id:3d}  {label}")
        except Exception as exc:  # noqa: BLE001
            print(f"{channel:<6} {'—':>3}  BUS {type(exc).__name__}: {exc}")
        finally:
            if bus is not None:
                try:
                    bus.stop()
                except Exception:  # noqa: BLE001
                    pass

    print("-" * 28)
    print(f"{online} / {tried} Recoil pings answered")
    return 0 if online else 1


if __name__ == "__main__":
    raise SystemExit(main())
