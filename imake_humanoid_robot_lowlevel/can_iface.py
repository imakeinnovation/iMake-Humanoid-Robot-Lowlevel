# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""SocketCAN interface checks used by ping and other motor tools."""

from __future__ import annotations

import errno
from pathlib import Path


IFF_UP = 0x1

# linux/can/error.h — SocketCAN error-class bits in the CAN ID
CAN_ERR_TX_TIMEOUT = 0x00000001
CAN_ERR_LOSTARB = 0x00000002
CAN_ERR_CRTL = 0x00000004
CAN_ERR_PROT = 0x00000008
CAN_ERR_TRX = 0x00000010
CAN_ERR_ACK = 0x00000020
CAN_ERR_BUSOFF = 0x00000040
CAN_ERR_BUSERROR = 0x00000080
CAN_ERR_RESTARTED = 0x00000100

_CAN_ERR_NAMES = (
    (CAN_ERR_TX_TIMEOUT, "TX_TIMEOUT"),
    (CAN_ERR_LOSTARB, "LOSTARB"),
    (CAN_ERR_CRTL, "CRTL"),
    (CAN_ERR_PROT, "PROT"),
    (CAN_ERR_TRX, "TRX"),
    (CAN_ERR_ACK, "ACK"),
    (CAN_ERR_BUSOFF, "BUSOFF"),
    (CAN_ERR_BUSERROR, "BUSERROR"),
    (CAN_ERR_RESTARTED, "RESTARTED"),
)


def describe_socketcan_error(arbitration_id: int) -> str:
    """Decode a SocketCAN error-frame CAN ID (e.g. 36 = ACK+CRTL)."""
    flags = [name for bit, name in _CAN_ERR_NAMES if arbitration_id & bit]
    joined = "+".join(flags) if flags else f"unknown(0x{arbitration_id:x})"
    return f"0x{arbitration_id:x} {joined}"


def is_ack_error(arbitration_id: int) -> bool:
    return bool(arbitration_id & CAN_ERR_ACK)


def motor_offline_hint(channel: str, device_id: int) -> str:
    return (
        f"Motor is offline ({channel} id {device_id})\n"
        "\n"
        "The SocketCAN interface is UP, but no actuator acknowledged the ping.\n"
        "Error Frame 36 is ACK+CRTL: this PC transmitted, nobody on the bus ACKed.\n"
        "\n"
        "Check, in order:\n"
        "  1. Actuators on this bus are powered.\n"
        "  2. CANH/CANL wiring and 120 ohm termination.\n"
        "  3. Bitrate is 1 Mbps (same as the motors).\n"
        "  4. This motor may not be on this interface:\n"
        "       Berkeley legs: left=can2 ids 1,3,5,7,11,13  right=can3 ids 2,4,6,8,12,14\n"
        "       iMAKE Humanoid(): left=can0  right=can1  (same ids)\n"
        f"     Try: python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can0 --id {device_id}\n"
        f"  5. ip -s -details link show {channel}\n"
    )


def socketcan_status(channel: str) -> str:
    """Return 'missing', 'down', or 'up' for a SocketCAN netdev."""
    net = Path("/sys/class/net") / channel
    if not net.is_dir():
        return "missing"
    flags_path = net / "flags"
    try:
        flags = int(flags_path.read_text().strip(), 0)
    except (OSError, ValueError):
        return "missing"
    return "up" if flags & IFF_UP else "down"


def is_network_down(exc: BaseException | None, _seen: set[int] | None = None) -> bool:
    if exc is None:
        return False
    seen = _seen if _seen is not None else set()
    marker = id(exc)
    if marker in seen:
        return False
    seen.add(marker)
    if isinstance(exc, OSError) and exc.errno in (errno.ENETDOWN, 100):
        return True
    text = str(exc).lower()
    if "network is down" in text or "enetdown" in text:
        return True
    return is_network_down(exc.__cause__, seen) or is_network_down(exc.__context__, seen)


def missing_interface_hint(channel: str) -> str:
    return (
        f"CAN interface {channel} was not found.\n"
        "\n"
        "Check adapters, then bring up whatever buses exist:\n"
        "  ip link show\n"
        "  source ./scripts/start_can_transports.sh\n"
        f"  ip link show {channel}\n"
    )


def network_down_hint(channel: str) -> str:
    return (
        f"CAN interface {channel} is down (ENETDOWN / Network is down).\n"
        "Python and python-can are fine; the SocketCAN netdev is not UP.\n"
        "\n"
        "Bring it up, then ping again:\n"
        "  source ./scripts/start_can_transports.sh\n"
        f"  ip link show {channel}\n"
        "\n"
        "Or only this bus at 1 Mbps:\n"
        f"  sudo ip link set {channel} down\n"
        f"  sudo ip link set {channel} up type can bitrate 1000000\n"
        f"  ip -details link show {channel}\n"
        "\n"
        "Then:\n"
        f"  export PYTHONPATH=\"$PWD\"\n"
        f"  python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --channel {channel} --id 1\n"
    )


def run_ping() -> int:
    """Ping one actuator. Returns a process exit code."""
    import sys

    import imake_humanoid_robot_lowlevel.recoil as recoil

    args = recoil.util.get_args()
    channel = args.channel
    device_id = args.id

    status = socketcan_status(channel)
    if status == "missing":
        sys.stderr.write(missing_interface_hint(channel))
        return 1
    if status == "down":
        sys.stderr.write(network_down_hint(channel))
        return 1

    bus = None
    try:
        bus = recoil.Bus(channel=channel, bitrate=1000000)
        online = bool(bus.ping(device_id))
    except Exception as exc:  # noqa: BLE001 — operator-facing CAN/OS errors
        if is_network_down(exc):
            sys.stderr.write(network_down_hint(channel))
            return 1
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        return 1
    finally:
        if bus is not None:
            try:
                bus.stop()
            except Exception:  # noqa: BLE001
                pass

    if online:
        print(f"Motor is online  ({channel} id {device_id})")
        return 0
    print(motor_offline_hint(channel, device_id), end="")
    return 0
