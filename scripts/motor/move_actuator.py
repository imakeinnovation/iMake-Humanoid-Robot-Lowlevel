# Copyright (c) 2025, The iMake Humanoid Robot Project Developers.

from pathlib import Path
import sys
import time

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import numpy as np
except ModuleNotFoundError as exc:
    raise SystemExit(
        "No module named 'numpy'. On Ubuntu 24 do not use pip on system Python.\n"
        "  sudo apt install python3-numpy\n"
        "Then retry:\n"
        "  python3 ./scripts/motor/move_actuator.py -c can1 -i 3"
    ) from exc

try:
    from loop_rate_limiters import RateLimiter
except ModuleNotFoundError:
    class RateLimiter:
        def __init__(self, frequency: float):
            self._dt = 1.0 / frequency
            self._next = time.perf_counter()

        def sleep(self) -> None:
            now = time.perf_counter()
            wait = self._next - now
            if wait > 0:
                time.sleep(wait)
            self._next += self._dt
            if self._next < now:
                self._next = now + self._dt

import imake_humanoid_robot_lowlevel.recoil as recoil


args = recoil.util.get_args()
bus = recoil.Bus(channel=args.channel, bitrate=1000000)

device_id = args.id

kp = 20.0
kd = 2.0

frequency = 1.0  # motion frequency is 1 Hz
amplitude = 1.0  # motion amplitude is 1 rad

rate = RateLimiter(frequency=200.0)


bus.write_position_kp(device_id, kp)
bus.write_position_kd(device_id, kd)
bus.write_torque_limit(device_id, 4.0)

bus.set_mode(device_id, recoil.Mode.POSITION)
bus.feed(device_id)

try:
    while True:
        target_angle = np.sin(2 * np.pi * frequency * time.time()) * amplitude

        measured_position, measured_velocity = bus.write_read_pdo_2(device_id, target_angle, 0.0)
        if measured_position is not None and measured_velocity is not None:
            print(f"Measured pos: {measured_position:.3f} \tvel: {measured_velocity:.3f}")

        rate.sleep()

except KeyboardInterrupt:
    pass

bus.set_mode(device_id, recoil.Mode.IDLE)
bus.stop()
