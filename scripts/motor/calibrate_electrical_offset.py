# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

from pathlib import Path
import sys
import time

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import imake_humanoid_robot_lowlevel.recoil as recoil


args = recoil.util.get_args()
bus = recoil.Bus(channel=args.channel, bitrate=1000000)

device_id = args.id

bus.set_mode(device_id, recoil.Mode.CALIBRATION)

# the motor should now perform the calibration sequence

# wait for calibration to finish
time.sleep(20)

bus.stop()
