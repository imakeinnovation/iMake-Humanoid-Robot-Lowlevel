"""
calibrate_joints.py

Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

Run this script after each power cycle to calibrate the encoder offset of each joint.
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
