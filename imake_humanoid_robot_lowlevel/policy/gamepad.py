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

    # If an axis hasn't produced a fresh reading in this long, its command is
    # forced back to 0 (see _watchdog_forever). advance() only recomputes
    # commands when get_gamepad() returns a new event, so a stick that stops
    # reporting changes for any reason (hysteresis on release, USB dropout,
    # a stuck pot) would otherwise leave its last nonzero command in effect
    # forever.
    _STALE_TIMEOUT_S = 0.3
    _STALE_CHECK_INTERVAL_S = 0.05

    _AXIS_TO_COMMAND = {
        XInputEntry.AXIS_Y_L: "velocity_x",
        XInputEntry.AXIS_X_R: "velocity_y",
        XInputEntry.AXIS_X_L: "velocity_yaw",
    }

    def __init__(self,
                 stick_sensitivity: float = 1.0,
                 dead_zone: float = 0.05,
                 ) -> None:
        self.stick_sensitivity = stick_sensitivity
        self.dead_zone = dead_zone

        self._stopped = threading.Event()
        self._run_forever_thread = None
        self._watchdog_thread = None

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
            XInputEntry.AXIS_Y_L: None,
            XInputEntry.AXIS_X_R: None,
            XInputEntry.AXIS_X_L: None,
        }
        self._axis_center_samples = {
            XInputEntry.AXIS_Y_L: [],
            XInputEntry.AXIS_X_R: [],
            XInputEntry.AXIS_X_L: [],
        }

        # Last time each axis actually received a new raw event, used by
        # _watchdog_forever to zero out commands whose axis has gone quiet
        # instead of holding their last (possibly nonzero) value forever.
        self._axis_last_update = {
            XInputEntry.AXIS_Y_L: time.monotonic(),
            XInputEntry.AXIS_X_R: time.monotonic(),
            XInputEntry.AXIS_X_L: time.monotonic(),
        }

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
        self._watchdog_thread = threading.Thread(target=self._watchdog_forever, daemon=True)
        self._watchdog_thread.start()

    def run_forever(self) -> None:
        while not self._stopped.is_set():
            self.advance()

    def _watchdog_forever(self) -> None:
        while not self._stopped.wait(self._STALE_CHECK_INTERVAL_S):
            now = time.monotonic()
            for code, command_key in self._AXIS_TO_COMMAND.items():
                if now - self._axis_last_update[code] > self._STALE_TIMEOUT_S:
                    self.commands[command_key] = 0.0

    def advance(self) -> None:
        events = get_gamepad()

        # update all events from the joystick
        for event in events:
            self._states[event.code] = event.state
            if event.code in self._axis_last_update:
                self._axis_last_update[event.code] = time.monotonic()

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
        if deviation >= 0:
            self._axis_scale_pos[code] = max(self._axis_scale_pos[code], deviation)
            scale = self._axis_scale_pos[code]
        else:
            self._axis_scale_neg[code] = max(self._axis_scale_neg[code], -deviation)
            scale = self._axis_scale_neg[code]

        value = -deviation / scale * self.stick_sensitivity
        if abs(value) < self.dead_zone:
            value = 0.0
        return max(-1.0, min(1.0, value))

    def _update_command_buffer(self) -> Dict[str, float]:
        now = time.monotonic()
        for code, command_key in self._AXIS_TO_COMMAND.items():
            raw = self._states.get(code)
            if raw is None:
                continue
            # An unrelated event (e.g. a different stick moving) also lands
            # here, so a stale axis must be re-checked on every call rather
            # than just once in the watchdog: otherwise recomputing from its
            # old raw value would immediately undo the watchdog's zeroing.
            if now - self._axis_last_update[code] > self._STALE_TIMEOUT_S:
                self.commands[command_key] = 0.0
            else:
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

    try:
        while True:
            print(f"""{command_controller.commands.get("velocity_x"):.2f}, {command_controller.commands.get("velocity_y"):.2f}, {command_controller.commands.get("velocity_yaw"):.2f}""")
            pass
    except KeyboardInterrupt:
        print("Keyboard interrupt")

    command_controller.stop()
