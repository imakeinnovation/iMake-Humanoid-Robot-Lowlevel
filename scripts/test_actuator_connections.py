#!/usr/bin/env python3
# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""Ping each biped actuator over SocketCAN.

This diagnostic opens CAN buses and calls Bus.ping() only. It does not
initialize the IMU, gamepad, calibration file, or locomotion controller,
and it does not change actuator modes or command motion.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import imake_humanoid_robot_lowlevel.recoil as recoil

BITRATE = 1_000_000

# iMAKE Humanoid.joints mapping (legs on can0/can1).
IMAKE_ACTUATORS: list[tuple[str, list[tuple[int, str]]]] = [
    (
        "can0",
        [
            (1, "left_hip_roll"),
            (3, "left_hip_yaw"),
            (5, "left_hip_pitch"),
            (7, "left_knee_pitch"),
            (11, "left_ankle_pitch"),
            (13, "left_ankle_roll"),
        ],
    ),
    (
        "can1",
        [
            (2, "right_hip_roll"),
            (4, "right_hip_yaw"),
            (6, "right_hip_pitch"),
            (8, "right_knee_pitch"),
            (12, "right_ankle_pitch"),
            (14, "right_ankle_roll"),
        ],
    ),
]

# Original Berkeley wiring still used on the robot computer (legs on can2/can3).
BERKELEY_ACTUATORS: list[tuple[str, list[tuple[int, str]]]] = [
    (
        "can2",
        [
            (1, "left_hip_roll"),
            (3, "left_hip_yaw"),
            (5, "left_hip_pitch"),
            (7, "left_knee_pitch"),
            (11, "left_ankle_pitch"),
            (13, "left_ankle_roll"),
        ],
    ),
    (
        "can3",
        [
            (2, "right_hip_roll"),
            (4, "right_hip_yaw"),
            (6, "right_hip_pitch"),
            (8, "right_knee_pitch"),
            (12, "right_ankle_pitch"),
            (14, "right_ankle_roll"),
        ],
    ),
]

EXPECTED_ACTUATORS = IMAKE_ACTUATORS
LAYOUTS = {
    "imake": IMAKE_ACTUATORS,
    "berkeley": BERKELEY_ACTUATORS,
}


def _format_result(device_id: int, name: str, status: str) -> str:
    return f"ID {device_id:2d}  {name:<22}  {status}"


def resolve_buses(layout: str = "imake", bus: str | None = None) -> list[tuple[str, list[tuple[int, str]]]]:
    if layout not in LAYOUTS:
        raise ValueError(f"Unknown layout '{layout}'. Use: {', '.join(LAYOUTS)}")
    table = LAYOUTS[layout]
    if bus is None:
        return table
    filtered = [item for item in table if item[0] == bus]
    if not filtered:
        available = ", ".join(channel for channel, _ in table)
        raise ValueError(
            f"No actuators mapped on {bus} for layout '{layout}'. "
            f"Available: {available}. "
            "If legs are on can2/can3, retry with --layout berkeley."
        )
    return filtered


def ping_channel(
    channel: str,
    devices: list[tuple[int, str]],
    bitrate: int = BITRATE,
    timeout: float = 0.1,
) -> tuple[list[tuple[int, str, str]], str | None]:
    """Ping devices on one SocketCAN channel.

    Returns (rows, bus_error). rows is empty when the bus could not be opened.
    """
    bus = None
    try:
        bus = recoil.Bus(channel=channel, bitrate=bitrate)
    except Exception as exc:  # noqa: BLE001 — surface CAN/OS errors to the operator
        return [], f"{type(exc).__name__}: {exc}"

    rows: list[tuple[int, str, str]] = []
    try:
        for device_id, name in devices:
            try:
                ok = bool(bus.ping(device_id, timeout=timeout))
                rows.append((device_id, name, "OK" if ok else "FAIL"))
            except Exception as exc:  # noqa: BLE001
                from imake_humanoid_robot_lowlevel.can_iface import is_network_down

                if is_network_down(exc):
                    return [], f"{type(exc).__name__}: {exc}"
                rows.append((device_id, name, f"FAIL ({type(exc).__name__}: {exc})"))
    finally:
        try:
            bus.stop()
        except Exception:  # noqa: BLE001
            pass

    return rows, None


def run_actuator_connection_test(
    buses: list[tuple[str, list[tuple[int, str]]]] | None = None,
    bitrate: int = BITRATE,
    timeout: float = 0.1,
) -> tuple[int, str]:
    """Run the diagnostic. Returns (exit_code, report_text)."""
    if buses is None:
        buses = EXPECTED_ACTUATORS

    lines = [
        "iMAKE Humanoid Robot — Actuator Connection Test",
        "",
    ]
    failures: list[str] = []
    ok_count = 0
    total = 0

    for channel, devices in buses:
        total += len(devices)
        lines.append(f"Testing {channel}")
        lines.append("-" * 40)

        rows, bus_error = ping_channel(channel, devices, bitrate=bitrate, timeout=timeout)
        if bus_error is not None:
            lines.append(f"BUS ERROR: {bus_error}")
            for device_id, name in devices:
                lines.append(_format_result(device_id, name, "FAIL (bus unavailable)"))
                failures.append(f"{channel} ID {device_id} {name}")
            lines.append("")
            continue

        for device_id, name, status in rows:
            lines.append(_format_result(device_id, name, status))
            if status == "OK":
                ok_count += 1
            else:
                failures.append(f"{channel} ID {device_id} {name}")
        lines.append("")

    lines.append("Summary")
    lines.append("-" * 40)
    lines.append(f"{ok_count} / {total} actuators responding")
    if failures:
        lines.append("FAILED:")
        for item in failures:
            lines.append(f"  {item}")
        exit_code = 1
    else:
        lines.append("All expected actuators responded.")
        exit_code = 0

    return exit_code, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ping biped actuators over SocketCAN without commanding motion."
    )
    parser.add_argument(
        "--layout",
        choices=sorted(LAYOUTS),
        default="imake",
        help="can0/can1 (imake, default) or can2/can3 (berkeley robot-PC wiring)",
    )
    parser.add_argument(
        "--bus",
        "--port",
        dest="bus",
        default=None,
        help="Ping only this SocketCAN interface, e.g. can2",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.1,
        help="Per-actuator ping timeout in seconds (default: 0.1)",
    )
    args = parser.parse_args(argv)

    try:
        buses = resolve_buses(layout=args.layout, bus=args.bus)
    except ValueError as exc:
        parser.error(str(exc))

    exit_code, report = run_actuator_connection_test(buses=buses, timeout=args.timeout)
    sys.stdout.write(report)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
