# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""
Gamepad controller for iMake Humanoid Robot.

Reads events via the `inputs` library and produces SE(2) velocity commands plus
a mode switch. Linux USB pads (evdev) usually report analog sticks as unsigned
8-bit axes that rest at 128 and do not emit events while held still. Xbox/XInput
pads report signed 16-bit axes that rest at 0.

The Ubuntu lab machines were stuck on main because startup calibration treated
unseen axes as raw 0, so an 8-bit stick looked like a full-scale command. This
module only normalizes an axis after a real event has arrived, defaults to the
8-bit layout those pads use, and promotes to 16-bit if a value falls outside
0–255.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Mapping


# Linux evdev 8-bit sticks (the iMake lab pads).
_UINT8_CENTER = 128.0
_UINT8_HALF_RANGE = 127.0

# Xbox / XInput signed 16-bit sticks.
_INT16_CENTER = 0.0
_INT16_HALF_RANGE = 32767.0


class XInputEntry:
    """Standard gamepad button and axis codes used by the `inputs` library."""

    AXIS_X_L = "ABS_X"
    AXIS_Y_L = "ABS_Y"
    AXIS_TRIGGER_L = "ABS_Z"
    AXIS_X_R = "ABS_RX"
    AXIS_Y_R = "ABS_RY"
    AXIS_TRIGGER_R = "ABS_RZ"

    BTN_HAT_X = "ABS_HAT0X"
    BTN_HAT_Y = "ABS_HAT0Y"

    BTN_A = "BTN_SOUTH"
    BTN_B = "BTN_EAST"
    BTN_X = "BTN_NORTH"
    BTN_Y = "BTN_WEST"
    BTN_BUMPER_L = "BTN_TL"
    BTN_BUMPER_R = "BTN_TR"
    BTN_THUMB_L = "BTN_THUMBL"
    BTN_THUMB_R = "BTN_THUMBR"
    BTN_BACK = "BTN_SELECT"
    BTN_START = "BTN_START"


_CONTROL_CODES = tuple(
    value for name, value in vars(XInputEntry).items()
    if not name.startswith("_") and isinstance(value, str)
)


def infer_axis_layout(raw: int) -> str:
    """Return ``uint8`` for Linux 0–255 pads, ``int16`` otherwise."""
    if 0 <= raw <= 255:
        return "uint8"
    return "int16"


def layout_defaults(layout: str) -> tuple[float, float, float]:
    """Return ``(center, scale_pos, scale_neg)`` for a known stick layout."""
    if layout == "int16":
        return _INT16_CENTER, _INT16_HALF_RANGE, _INT16_HALF_RANGE
    return _UINT8_CENTER, _UINT8_HALF_RANGE, _UINT8_HALF_RANGE


def probe_linux_axis_limits() -> dict[str, tuple[float, float]]:
    """Read kernel AbsInfo min/max for the first gamepad, if evdev is available."""
    try:
        from evdev import InputDevice, ecodes, list_devices
    except ImportError:
        return {}

    try:
        device_paths = list_devices()
    except OSError:
        return {}

    for path in device_paths:
        try:
            device = InputDevice(path)
            abs_caps = device.capabilities(absinfo=True).get(ecodes.EV_ABS) or []
        except (OSError, TypeError, ValueError):
            continue
        limits: dict[str, tuple[float, float]] = {}
        abs_names = getattr(ecodes, "ABS", {})
        for item in abs_caps:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            code, info = item
            name = abs_names.get(code, "")
            if isinstance(name, (list, tuple)):
                name = name[0] if name else ""
            if not name or not hasattr(info, "min"):
                continue
            limits[str(name)] = (float(info.min), float(info.max))
        if "ABS_X" in limits and "ABS_Y" in limits:
            return limits
    return {}


class Se2Gamepad:
    _AXIS_TO_COMMAND = {
        XInputEntry.AXIS_Y_L: "velocity_x",
        XInputEntry.AXIS_X_R: "velocity_y",
        XInputEntry.AXIS_X_L: "velocity_yaw",
    }

    def __init__(
        self,
        stick_sensitivity: float = 1.0,
        dead_zone: float = 0.1,
        axis_limits: Mapping[str, tuple[float, float]] | None = None,
    ) -> None:
        self.stick_sensitivity = stick_sensitivity
        self.dead_zone = dead_zone

        self._stopped = threading.Event()
        self._run_forever_thread = None

        probed = dict(axis_limits) if axis_limits is not None else probe_linux_axis_limits()
        self._axis_limits = probed

        self._axis_layout: dict[str, str] = {}
        self._axis_scale_pos: dict[str, float] = {}
        self._axis_scale_neg: dict[str, float] = {}
        self._axis_center: dict[str, float] = {}
        self._axis_seen: set[str] = set()
        for code in self._AXIS_TO_COMMAND:
            self._apply_layout(code, self._initial_layout(code))

        # Edge-detects BTN_BACK so recalibration fires once per press.
        self._recalibrate_button_was_pressed = False

        self.reset()

        self.commands = {
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "velocity_yaw": 0.0,
            "mode_switch": 0,
        }

    def _initial_layout(self, code: str) -> str:
        if code in self._axis_limits:
            lo, hi = self._axis_limits[code]
            if lo < 0 or hi > 255:
                return "int16"
            return "uint8"
        # iMake lab Ubuntu pads are 8-bit evdev sticks that rest at 128.
        return "uint8"

    def _apply_layout(self, code: str, layout: str) -> None:
        if code in self._axis_limits:
            lo, hi = self._axis_limits[code]
            center = (lo + hi) / 2.0
            self._axis_layout[code] = layout
            self._axis_center[code] = center
            self._axis_scale_pos[code] = max(hi - center, 1.0)
            self._axis_scale_neg[code] = max(center - lo, 1.0)
            return
        center, scale_pos, scale_neg = layout_defaults(layout)
        self._axis_layout[code] = layout
        self._axis_center[code] = center
        self._axis_scale_pos[code] = scale_pos
        self._axis_scale_neg[code] = scale_neg

    def reset(self) -> None:
        self._states = {code: 0 for code in _CONTROL_CODES}
        self._axis_seen.clear()

    def stop(self) -> None:
        print("Gamepad stopping...")
        self._stopped.set()

    def run(self) -> None:
        self._run_forever_thread = threading.Thread(target=self.run_forever, daemon=True)
        self._run_forever_thread.start()

    def run_forever(self) -> None:
        while not self._stopped.is_set():
            self.advance()

    def advance(self, events=None) -> None:
        if events is None:
            from inputs import get_gamepad
            events = get_gamepad()

        for event in events:
            self._states[event.code] = event.state
            if event.code in self._AXIS_TO_COMMAND:
                self._axis_seen.add(event.code)

        self._update_command_buffer()

    def _normalize_axis(self, code: str, raw: int) -> float:
        """Normalize a raw axis reading to [-1, 1]."""
        observed_layout = infer_axis_layout(raw)
        if observed_layout == "int16" and self._axis_layout[code] != "int16":
            self._apply_layout(code, "int16")

        center = self._axis_center[code]
        deviation = raw - center
        scale_map = self._axis_scale_pos if deviation >= 0 else self._axis_scale_neg
        scale_map[code] = max(scale_map[code], abs(deviation), 1.0)
        scale = scale_map[code]

        value = -deviation / scale * self.stick_sensitivity
        if abs(value) < self.dead_zone:
            value = 0.0
        return max(-1.0, min(1.0, value))

    def _reset_axis_calibration(self) -> None:
        """Restore layout defaults. Hold sticks at rest, then press Back/Select."""
        print("Gamepad: recalibrating stick center/range, hold sticks at rest...")
        self._axis_seen.clear()
        for code in self._AXIS_TO_COMMAND:
            self._apply_layout(code, self._initial_layout(code))

    def _update_command_buffer(self) -> Dict[str, float]:
        recalibrate_button_pressed = bool(self._states.get(XInputEntry.BTN_BACK))
        if recalibrate_button_pressed and not self._recalibrate_button_was_pressed:
            self._reset_axis_calibration()
        self._recalibrate_button_was_pressed = recalibrate_button_pressed

        for code, command_key in self._AXIS_TO_COMMAND.items():
            if code not in self._axis_seen:
                self.commands[command_key] = 0.0
                continue
            raw = self._states.get(code)
            if raw is not None:
                self.commands[command_key] = self._normalize_axis(code, raw)

        mode_switch = 0

        # Enter RL control mode (A + Right Bumper)
        if self._states.get(XInputEntry.BTN_A) and self._states.get(XInputEntry.BTN_BUMPER_R):
            mode_switch = 3

        # Enter init mode (A + Left Bumper)
        if self._states.get(XInputEntry.BTN_A) and self._states.get(XInputEntry.BTN_BUMPER_L):
            mode_switch = 2

        # Enter idle mode (B, X, or either thumbstick click)
        if (
            self._states.get(XInputEntry.BTN_B)
            or self._states.get(XInputEntry.BTN_X)
            or self._states.get(XInputEntry.BTN_THUMB_L)
            or self._states.get(XInputEntry.BTN_THUMB_R)
        ):
            mode_switch = 1

        self.commands["mode_switch"] = mode_switch
        return self.commands


if __name__ == "__main__":
    command_controller = Se2Gamepad()
    command_controller.run()

    axis_labels = [
        (XInputEntry.AXIS_Y_L, "Y_L(fwd/back)"),
        (XInputEntry.AXIS_X_L, "X_L(yaw)     "),
        (XInputEntry.AXIS_X_R, "X_R(strafe)  "),
    ]

    try:
        while True:
            for code, label in axis_labels:
                raw = command_controller._states.get(code)
                seen = code in command_controller._axis_seen
                center = command_controller._axis_center[code]
                scale_pos = command_controller._axis_scale_pos[code]
                scale_neg = command_controller._axis_scale_neg[code]
                seen_str = "yes" if seen else "no"
                print(
                    f"  {label}  raw={raw:>6}  seen={seen_str:>3}  "
                    f"center={center:>8.1f}  scale_pos={scale_pos:>8.1f}  "
                    f"scale_neg={scale_neg:>8.1f}"
                )
            print(
                f"""  commands: x={command_controller.commands.get("velocity_x"):.2f}  """
                f"""y={command_controller.commands.get("velocity_y"):.2f}  """
                f"""yaw={command_controller.commands.get("velocity_yaw"):.2f}  """
                f"""mode={command_controller.commands.get("mode_switch")}"""
            )
            print("-" * 70)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Keyboard interrupt")

    command_controller.stop()
