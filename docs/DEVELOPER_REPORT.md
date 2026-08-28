# Developer status report — low-level / robot PC

**Date:** 2026-08-28  
**Branch:** `ubuntu`  
**Host context:** iMAKE lab robot PC (`imakeinnovationcnter@iMakeHumanoid`)

This is the plain-language developer overview of the **low-level** tree and
current lab hardware state. For the operator log and command catalog, see
[STATUS.md](STATUS.md) and [BRINGUP.md](BRINGUP.md).


## One-sentence bottom line

Software for talking to motors over SocketCAN is on GitHub and usable. The
physical biped is **not walkable** — only **one** Recoil actuator has answered
ping. Do **not** run `Humanoid()`, joint calibration, or RL until more
actuators are online.


## What this package is

Python package `imake_humanoid_robot_lowlevel` (derived from Berkeley Humanoid
Lite) runs on the **robot PC**. It covers:

| Layer | Main pieces | Job |
| --- | --- | --- |
| SocketCAN helpers | `can_iface.py`, `scripts/start_can_transports.sh`, `up_can.sh` | Bring USB-CAN up at 1 Mbps; explain DOWN / ACK / queue errors |
| Recoil protocol | `recoil/` | Packet format and bus I/O for STM32 motor controllers |
| Single-motor tools | `motor/ping.py`, `scripts/jog_actuator.py`, electrical-offset / phase-order scripts | Prove one motor is alive, calibrate commutation, jog gently |
| Whole robot | `robot/humanoid.py`, `imu.py` | Expects `can0` (left) + `can1` (right) with the full biped ID map — **not safe yet** |
| Operator input | `policy/gamepad.py` | Linux USB pads (8-bit) and Xbox-style 16-bit sticks |
| Policy runner | `policy/rl_controller.py`, `scripts/run_locomotion.py` | RL locomotion once the robot stack is online |

Parent monorepo also has Isaac Lab training and assets. Only **this** tree is
required on the robot PC.


## Git state (as of this report)

| Item | Value |
| --- | --- |
| Repo | [imakeinnovation/iMake-Humanoid-Robot-Lowlevel](https://github.com/imakeinnovation/iMake-Humanoid-Robot-Lowlevel) |
| Working branch | `ubuntu` |
| Lab bring-up PR | [#2](https://github.com/imakeinnovation/iMake-Humanoid-Robot-Lowlevel/pull/2) (merged) |
| Related parent PR | [iMake-Humanoid-Robot #2](https://github.com/imakeinnovation/iMake-Humanoid-Robot/pull/2) (merged) |

Day-to-day lab source of truth: **`ubuntu`**, not `main`.


## What the 2026-08-27 bring-up fixed in software

### Packaging (Ubuntu 24)

- System `python3` + apt `python3-can` / `python3-numpy`
- Path bootstrap so ping works without installing onto system Python with
  `--break-system-packages`
- Optional venv with `--system-site-packages` for `loop-rate-limiters`

### SocketCAN

- Sourced bring-up scripts no longer kill the SSH session
- Missing buses report `MISSING`
- Ping explains `Network is down`, ACK error frame **36**, and TX queue full
  instead of dumping a traceback

### Actuator bench tools

| Script | Purpose |
| --- | --- |
| `scripts/calibrate_electrical_offset.py` | One Recoil `MODE_CALIBRATION` (~20 s). Do not Ctrl+C. |
| `scripts/jog_actuator.py` | Slow sine **around the current encoder** |
| `scripts/motor/move_actuator.py` | Sine **around 0** — wrong if encoder is near 3 rad |
| `scripts/set_phase_order.py` | CAN `phase_order` read/write. **Does not** reverse first calib spin. |
| `scripts/scan_ids.py` / `scan_motors.sh` | Ping biped ids on every UP bus (no motion) |
| `scripts/test_actuator_connections.py` | `--layout imake` (can0/can1) |

### Gamepad

Lab USB pads often rest at raw **128** (8-bit). Startup calibration now waits
for real axis events and defaults to that layout so sticks do not look like
full-scale commands at rest.


## Hardware / lab reality

| Area | State |
| --- | --- |
| Python + SocketCAN software | Working |
| First Recoil | **can1 id 3** → `Motor is online` |
| Rest of biped | Offline when last scanned (only one CAN cable on a motor) |
| USB-CAN names | Unstable after unplug/replug; may come back **DOWN** or as **can0** |
| Electrical offset on id 3 | Ran; first spin was **CW then CCW** (docs want **CCW then CW**) |
| CAN `phase_order` +1 → −1 | Did **not** reverse first spin |
| `Humanoid()` / IMU / RL | Not started — blocked |

### Intended map when fully wired

| Bus | Leg | IDs |
| --- | --- | --- |
| **can0** | Left | 1, 3, 5, 7, 11, 13 (`id 3` = `left_hip_yaw`) |
| **can1** | Right | 2, 4, 6, 8, 12, 14 |

Today id 3 answered on **can1** only because that was the live cable. Do **not**
remap `Humanoid()` to chase a temporary dongle name.


## Recommended next work (in order)

1. After every USB change: `ip -br link show type can`, bring the live iface UP
   at 1 Mbps, `txqueuelen 1000`, ping one id.
2. Finish actuator 3: restore `phase_order` +1 if needed; power off; swap **two
   motor phase wires** (not CAN); re-run electrical offset (CCW first); jog with
   `jog_actuator.py`.
3. Bring up remaining actuators **one at a time** (ping → offset → jog), then
   the other leg.
4. When **12** biped actuators ping on can0 and can1:
   - `scripts/test_actuator_connections.py --layout imake`
   - `calibrate_joints.py`
   - IMU + gamepad checks
   - Idle / damping, then RL

### Do not change yet

Recoil ping payload `0xCA`, actuator IDs, joint order, RL gains in
`Humanoid()`, or IMU transforms. Fix wiring and commutation direction first.


## Where to read next

| Doc | Use |
| --- | --- |
| [STATUS.md](STATUS.md) | Short status snapshot (2026-08-27) |
| [BRINGUP.md](BRINGUP.md) | Commands, error catalog, what was tried |
| [../README.md](../README.md) | Install + everyday robot-PC workflow |
| Parent monorepo report | `docs/DEVELOPER_REPORT.md` in [iMake-Humanoid-Robot](https://github.com/imakeinnovation/iMake-Humanoid-Robot) |
