# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

from imake_humanoid_robot_lowlevel.robot import Humanoid


robot = Humanoid()

robot.check_connection()

robot.stop()
