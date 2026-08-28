"""
test_joystick.py

Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

Print live gamepad commands. Useful for checking stick calibration on Linux
evdev pads before running locomotion.
"""

from imake_humanoid_robot_lowlevel.robot import Humanoid

ROBOT = Humanoid()

while True:
    print(
        ROBOT.command_controller.commands["mode_switch"],
        ROBOT.command_controller.commands["velocity_x"],
        ROBOT.command_controller.commands["velocity_y"],
        ROBOT.command_controller.commands["velocity_yaw"]
    )
