# iMake Humanoid Robot Low-level Control

Python package `imake_humanoid_robot_lowlevel`: Recoil SocketCAN transport,
robot I/O, gamepad, and policy runner.

Derived from [Berkeley Humanoid Lite](https://github.com/HybridRobotics/berkeley-humanoid-lite).

**Developer report:** [docs/DEVELOPER_REPORT.md](docs/DEVELOPER_REPORT.md).
**Status snapshot:** [docs/STATUS.md](docs/STATUS.md).
**Lab bring-up log:** [docs/BRINGUP.md](docs/BRINGUP.md).
Read those before flashing Recoil or swapping motor wires.


## Working directory

On the robot PC:

```bash
cd ~/iMake-Humanoid-Robot/source/imake_humanoid_robot_lowlevel
export PYTHONPATH="$PWD"
```

Use **system** `python3` plus Debian packages. Ubuntu 24 blocks `pip` on
system Python (`externally-managed-environment`). Do **not** use
`--break-system-packages`.

```bash
sudo apt install net-tools can-utils python3-can python3-numpy python3-venv python3-full
```

Optional venv (needed for `loop-rate-limiters` on jog/move if apt does not
provide it). Keep apt `python-can` / `numpy` visible:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

`pip install -e .` reads `pyproject.toml`. Do not treat `requirements.txt` as
a second install path.

Confirm imports:

```bash
python3 -c "import can, numpy, imake_humanoid_robot_lowlevel.recoil; print('OK')"
```


## Current lab state

| | |
| --- | --- |
| First Recoil that ACKed | **can1 id 3** (`Motor is online`) |
| Other biped ids on that bus | Offline when last scanned |
| USB-CAN names | Unstable. One dongle may come back as **can0**. Check `ip -br link show type can` every time. |
| Electrical offset on id 3 | Ran. First spin was **CW then CCW** (docs want **CCW then CW**). |
| CAN `phase_order` +1 → −1 | **Did not** reverse that first spin. See [docs/BRINGUP.md](docs/BRINGUP.md). |
| `Humanoid()` buses | Still **can0** (left) and **can1** (right). Do not remap yet. |


## Bring up CAN

```bash
source ./scripts/start_can_transports.sh
ip -br link show type can
```

The script is safe to `source` (it will not exit SSH). It brings up whichever
of `can0`–`can3` exist at **1 Mbps**. Missing buses print `MISSING`.

If an iface exists but is **DOWN** (`qdisc noop`, `Network is down`):

```bash
sudo ip link set can1 down
sudo ip link set can1 up type can bitrate 1000000 restart-ms 100
sudo ip link set can1 txqueuelen 1000
ip -details link show can1
```

Skip `up type can` if it is already UP (`Device or resource busy`). After
unplug/replug, USB-CAN often comes back DOWN — run the down/up pair again.

Power order: STM32 on (green LED) → plug USB-C → iface UP → ping.


## Ping one motor

```bash
python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can1 --id 3
```

`--port` is an alias for `--channel`. You want `Motor is online (can1 id 3)`.

Scan every UP bus (no motion):

```bash
python3 ./scripts/scan_ids.py
# or
./scripts/scan_motors.sh
```

Full biped table (still no IMU / gamepad / motion):

```bash
python3 scripts/test_actuator_connections.py              # iMAKE: can0 / can1
python3 scripts/test_actuator_connections.py --layout berkeley  # old wiring: can2 / can3
```


## Electrical offset (one Recoil)

The shaft **spins** ~20 s. Joint must be free. Do **not** press Ctrl+C.
This is not `calibrate_joints.py`.

```bash
python3 ./scripts/calibrate_electrical_offset.py --channel can1 --id 3
```

Docs: first turn **CCW**, second **CW**. If it is **CW then CCW**, do **not**
expect `scripts/set_phase_order.py` to fix it — that only writes the live CAN
parameter. The documented fixes are: swap two **motor phase** (U/V/W) wires,
**or** reflash Recoil with `#define MOTOR_PHASE_ORDER -1`. Details:
[docs/BRINGUP.md](docs/BRINGUP.md#electrical-offset-and-phase-order).


## Visible bench motion

`move_actuator.py` commands **±1 rad about 0**. If the encoder is near 3 rad
you get vibration and almost no motion. Jog around the **current** pose:

```bash
python3 ./scripts/jog_actuator.py --channel can1 --id 3
```

Default: ±0.5 rad at 0.2 Hz, **kp=20, kd=2, torque=4**. Ctrl+C → IDLE.

If leftover jog/move fills the TX queue (`ENOBUFS` / Error 105): kill those
processes, cycle the iface, set `txqueuelen 1000`, ping **one** id.


## Do not run yet

Until several actuators ping online on the buses `Humanoid()` opens (**can0**
and **can1**):

- `python scripts/check_connection.py` (constructs `Humanoid()`)
- `python scripts/calibrate_joints.py`
- `python scripts/run_locomotion.py`
- `make run`

Do not change Recoil ping payload `0xCA`, actuator IDs, joint order, RL gains
in `Humanoid()`, or IMU transforms.


## Optional: full package install and Humanoid

After CAN ping works on the mapped buses:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e .
python scripts/check_connection.py
python scripts/test_joystick.py
python -m imake_humanoid_robot_lowlevel.policy.gamepad   # no CAN
```

Joint zero after each power cycle (needs Humanoid + gamepad):

```bash
python scripts/calibrate_joints.py
```

Move each joint to its mechanical limit, then `q` or **B** on the pad. Data
lands in `./calibration.yaml`.

C controller:

```bash
make run
```

`LB`+`A` RL init, `RB`+`A` RL running, **B** / **X** / stick click idle.
Back/Select recalibrates the pad. First Ctrl+C → damping; second → idle.


## License

MIT. Derived from Berkeley Humanoid Lite; keep original copyright notices.
