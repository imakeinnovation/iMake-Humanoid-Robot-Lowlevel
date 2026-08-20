# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

"""
Gamepad Controller Module for iMake Humanoid Robot

This module implements UDP-based controllers for the iMake Humanoid Robot,
supporting both gamepad and keyboard input devices. It handles command broadcasting
over UDP for robot control modes and movement velocities.
"""

import threading
import time
from typing import Dict

from inputs import get_gamepad


class XInputEntry:
    """
    Constants for gamepad button and axis mappings.

    This class defines the standard mapping for various gamepad controls,
    including analog sticks, triggers, d-pad, and buttons.
    """
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


class Se2Gamepad:
    # Number of raw readings to average per axis, at startup, to determine
    # its idle/rest value before any scale calibration or command output.
    _CENTER_CALIBRATION_SAMPLES = 20

    _AXIS_TO_COMMAND = {
        XInputEntry.AXIS_Y_L: "velocity_x",
        XInputEntry.AXIS_X_R: "velocity_y",
        XInputEntry.AXIS_X_L: "velocity_yaw",
    }

    def __init__(self,
                 stick_sensitivity: float = 1.0,
                 dead_zone: float = 0.1,
                 ) -> None:
        self.stick_sensitivity = stick_sensitivity
        self.dead_zone = dead_zone

        self._stopped = threading.Event()
        self._run_forever_thread = None

        # Tracks the largest raw deviation from center seen on each axis so
        # far, self-calibrating the normalization range instead of assuming
        # a fixed 16-bit (Xbox/XInput) range that generic controllers don't
        # follow. Positive and negative deflection are tracked separately:
        # cheap sticks are often not symmetric (mechanical stop closer on
        # one side, or a worn/off-axis pot), so sharing a single scale would
        # make the direction with less physical travel normalize too weak
        # to clear the dead zone even at full deflection.
        self._axis_scale_pos = {
            XInputEntry.AXIS_Y_L: 1.0,
            XInputEntry.AXIS_X_R: 1.0,
            XInputEntry.AXIS_X_L: 1.0,
        }
        self._axis_scale_neg = {
            XInputEntry.AXIS_Y_L: 1.0,
            XInputEntry.AXIS_X_R: 1.0,
            XInputEntry.AXIS_X_L: 1.0,
        }

        # Each axis's idle/rest raw value, set once from the first
        # _CENTER_CALIBRATION_SAMPLES readings (None until then). Generic
        # pads often don't rest at exactly 0, and that offset gets amplified
        # once the scale calibrates down to a small real range, producing
        # phantom nonzero commands at rest. Assumes the stick is untouched
        # for the first moment after the controller connects.
        self._axis_center = {
            XInputEntry.AXIS_Y_L: 128,
            XInputEntry.AXIS_X_R: 128,
            XInputEntry.AXIS_X_L: 128,
        }
        self._axis_center_samples = {
            XInputEntry.AXIS_Y_L: [],
            XInputEntry.AXIS_X_R: [],
            XInputEntry.AXIS_X_L: [],
        }

        # Edge-detects BTN_BACK to trigger _reset_axis_calibration() once per
        # press (see _update_command_buffer), not continuously while held.
        self._recalibrate_button_was_pressed = False

        self.reset()

        self.commands = {
            "velocity_x": 0.0,
            "velocity_y": 0.0,
            "velocity_yaw": 0.0,
            "mode_switch": 0,
        }

    def reset(self) -> None:
        self._states = {key: 0 for key in XInputEntry.__dict__.values()}

    def stop(self) -> None:
        print("Gamepad stopping...")
        self._stopped.set()
        # self._run_forever_thread.join()

    def run(self) -> None:
        self._run_forever_thread = threading.Thread(target=self.run_forever)
        self._run_forever_thread.start()

    def run_forever(self) -> None:
        while not self._stopped.is_set():
            self.advance()

    def advance(self) -> None:
        events = get_gamepad()

        # update all events from the joystick
        for event in events:
            self._states[event.code] = event.state

        self._update_command_buffer()

    def _normalize_axis(self, code: str, raw: int) -> float:
        """Normalize a raw axis reading to [-1, 1], self-calibrating the idle
        center (first _CENTER_CALIBRATION_SAMPLES readings) and the
        max-deflection range in each direction independently (largest
        positive/negative deviation from center seen since)."""
        center = self._axis_center[code]
        if center is None:
            samples = self._axis_center_samples[code]
            samples.append(raw)
            if len(samples) < self._CENTER_CALIBRATION_SAMPLES:
                return 0.0
            center = sum(samples) / len(samples)
            self._axis_center[code] = center

        deviation = raw - center
        scale_map = self._axis_scale_pos if deviation >= 0 else self._axis_scale_neg
        scale_map[code] = max(scale_map[code], abs(deviation))
        scale = scale_map[code]

        value = -deviation / scale * self.stick_sensitivity
        if abs(value) < self.dead_zone:
            value = 0.0
        return max(-1.0, min(1.0, value))

    def _reset_axis_calibration(self) -> None:
        """Re-run startup center calibration and clear the learned
        max-deflection range on every axis. A one-off unrepresentative
        excursion (e.g. one hard, fast swing to correct drift) can otherwise
        permanently set the ceiling too high for genuine but more moderate
        pushes afterward; triggered manually (BTN_BACK) rather than an
        automatic heuristic, since telling a real outlier apart from
        ordinary input isn't reliably possible from raw readings alone."""
        print("Gamepad: recalibrating stick center/range, hold sticks at rest...")
        for code in self._AXIS_TO_COMMAND:
            self._axis_center[code] = None
            self._axis_center_samples[code] = []
            self._axis_scale_pos[code] = 1.0
            self._axis_scale_neg[code] = 1.0

    def _update_command_buffer(self) -> Dict[str, float]:
        recalibrate_button_pressed = bool(self._states.get(XInputEntry.BTN_BACK))
        if recalibrate_button_pressed and not self._recalibrate_button_was_pressed:
            self._reset_axis_calibration()
        self._recalibrate_button_was_pressed = recalibrate_button_pressed

        for code, command_key in self._AXIS_TO_COMMAND.items():
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

        # Enter idle mode (B or Left/Right Thumbstick)
        if self._states.get(XInputEntry.BTN_X) or self._states.get(XInputEntry.BTN_THUMB_L) or self._states.get(XInputEntry.BTN_THUMB_R):
            mode_switch = 1

        self.commands["mode_switch"] = mode_switch


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
                center = command_controller._axis_center[code]
                scale_pos = command_controller._axis_scale_pos[code]
                scale_neg = command_controller._axis_scale_neg[code]
                center_str = f"{center:.1f}" if center is not None else "calibrating"
                print(f"  {label}  raw={raw:>6}  center={center_str:>11}  scale_pos={scale_pos:>7.1f}  scale_neg={scale_neg:>7.1f}")
            print(f"""  commands: x={command_controller.commands.get("velocity_x"):.2f}  y={command_controller.commands.get("velocity_y"):.2f}  yaw={command_controller.commands.get("velocity_yaw"):.2f}""")
            print("-" * 70)
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Keyboard interrupt")

    command_controller.stop()
