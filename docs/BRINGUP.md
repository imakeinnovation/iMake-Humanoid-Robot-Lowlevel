# Robot PC bring-up (lab, 2026-08-27)

This is the operator record of CAN / Recoil bring-up on the iMAKE lab host
(`imakeinnovationcnter@iMakeHumanoid`). It is the source of truth for what
was tried, what was fixed in software, what the hardware actually is, and
what is still open.

Upstream flashing and electrical-offset **direction** notes live in the
[Berkeley Humanoid Lite docs](https://berkeley-humanoid-lite.gitbook.io/docs/getting-started-with-hardware/flashing-the-motor-controllers).
This tree does not contain that GitBook page. This file records what that
page means on **this** robot, plus every software fix from this session.

Work from:

```text
~/iMake-Humanoid-Robot/source/imake_humanoid_robot_lowlevel
```

Copy this tree onto the robot PC before expecting new scripts (`jog_actuator.py`,
`calibrate_electrical_offset.py` at `scripts/`, `set_phase_order.py`, …) to exist
there.


## Final state (end of 2026-08-27)

| Item | State |
| --- | --- |
| Python / ping imports | **Working.** Package on `PYTHONPATH`. System `python3` + `apt` `python3-can` / `python3-numpy`. Do **not** `pip` onto system Python (Ubuntu 24 PEP 668). |
| SocketCAN software | **Working.** `gs_usb` adapters at **1 Mbps**. Bring-up scripts no longer `exit` an SSH session. Ping decodes DOWN / missing / ACK errors instead of dumping a traceback. |
| First live Recoil | **`can1` id 3** printed `Motor is online`. Other biped ids on that bus (1, 2, 4–8, 11–14) were offline. |
| USB-CAN mapping | **Not stable.** Four USB-C dongles on a powered hub. Only **one** CAN cable went to a motor. Unplug test: that cable’s dongle was `can1`. After unplug/replug, Linux often brings the iface back **DOWN**, and a **single** remaining dongle may appear as **`can0`**, not `can1`. Always run `ip -br link show type can` before pinging. |
| Electrical offset | **Ran** on the live actuator. Shaft spun ~20 s. First rotation was **CW then CCW** (docs want **CCW then CW**). |
| CAN `MOTOR_PHASE_ORDER` +1 → −1 | **Did not reverse the first spin.** That write is Recoil parameter `0x10C`, stored to flash. Berkeley’s documented fix is either swap two **motor phase** wires, or change `#define MOTOR_PHASE_ORDER` **in Recoil firmware and reflash**. |
| `move_actuator.py` | **Commands ±1 rad about 0.** Encoder sat near **~3.19 rad**, so the joint vibrated and barely moved. Not a CAN failure. |
| Visible motion | Use `scripts/jog_actuator.py` (sine around **current** encoder). Gains used: **kp=20, kd=2, torque=4**. |
| `Humanoid()` / `calibrate_joints.py` / RL | **Do not run yet.** `Humanoid()` still opens **can0 / can1**. Need multiple actuators online on those buses first. |
| Do not change | Recoil ping payload `0xCA`, actuator IDs, joint order, RL gains in `Humanoid()`, IMU transforms. |


## Fixes shipped in this tree

These are the software changes from this bring-up. They do not replace wiring,
power, or Recoil firmware.

### Imports and packaging

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'imake_humanoid_robot_lowlevel'` | Ping and motor scripts put the low-level root on `sys.path`. `export PYTHONPATH="$PWD"` still works. Do **not** paste `import sys` into bash. |
| `No module named 'can'` on Ubuntu 24 | **Not** `pip` on system Python. `sudo apt install python3-can`. Hint in `ensure_deps.py`. Helper: `scripts/install_python_can.sh`. |
| `No module named 'numpy'` on `move_actuator.py` | `sudo apt install python3-numpy`. Script prints that hint. |
| Missing `loop_rate_limiters` | `move_actuator.py` falls back to a small local `RateLimiter`. Optional: venv with `--system-site-packages`. |
| `--port` rejected | `--port` is an alias for `--channel` on ping / calib / jog / phase-order. |

Ping wrappers (same command, three paths):

```text
./imake_humanoid_robot_lowlevel/motor/ping.py
./motor/ping.py
./scripts/motor/ping.py
```

There is **no** `./imake_humanoid_robot_lowlevel/scripts/motor/` tree. Do not
invent that path.

### SocketCAN

| Problem | Fix |
| --- | --- |
| `source` of bring-up killed the SSH session | `start_can_transports.sh` / `stop_can_transports.sh` / `up_can.sh` use `return` when sourced, `exit` when executed. |
| Missing `can2` looked like a mysterious `ip` failure | Scripts report **MISSING** for interfaces that are not present, and bring up whichever of `can0`–`can3` exist. |
| `Network is down` / `ENETDOWN` | Netdev exists but is **DOWN** (`qdisc noop`). Ping prints a bring-up hint instead of a traceback (`can_iface.py`). |
| Error frame **36** | SocketCAN **ACK+CRTL**: this PC transmitted, nobody ACKed. Software is done; the bus is electrically empty. |
| `ENOBUFS` / Error 105 | TX queue full (leftover jog/move, default `qlen 10`). Kill leftover Python, cycle the iface, set `txqueuelen 1000`, ping **one** id. |
| `Cannot find device "can1"` | USB-CAN unplugged; Linux re-enumerated. Check `ip -br link show type can`. |
| Error-frame flood hung `receive()` | Recoil `receive()` has a deadline; error prints are rate-limited. |

### Actuator tools added

| Script | What it does |
| --- | --- |
| `scripts/calibrate_electrical_offset.py` | One Recoil `MODE_CALIBRATION`, requires `--channel` and `--id`, pings first, waits 20 s. Do not Ctrl+C. |
| `scripts/motor/calibrate_electrical_offset.py` | Same Recoil command (older path). |
| `scripts/jog_actuator.py` | Slow sine **around the current encoder** (default ±0.5 rad at 0.2 Hz). |
| `scripts/motor/move_actuator.py` (and path wrappers) | Sine **around 0** at ±1 rad. Wrong tool if the encoder is near 3 rad. |
| `scripts/set_phase_order.py` | Reads/writes CAN `PARAM_MOTOR_PHASE_ORDER` (`0x10C`) and stores flash. **Does not reverse the first calib spin.** |
| `scripts/scan_ids.py` / `scripts/scan_motors.sh` | Ping biped ids on every UP bus. No motion. |
| `scripts/test_actuator_connections.py` | `--layout imake` (can0/can1) or `--layout berkeley` (can2/can3). |
| `scripts/up_can.sh` | Bring up one named iface at 1 Mbps. |

Move / jog gains were set toward Humanoid damping: **kp=20, kd=2, torque=4**.


## Commands that work on the robot PC

System `python3` (plus apt `python3-can`, `python3-numpy`):

```bash
cd ~/iMake-Humanoid-Robot/source/imake_humanoid_robot_lowlevel
export PYTHONPATH="$PWD"

ip -br link show type can
sudo ip link set can1 down
sudo ip link set can1 up type can bitrate 1000000 restart-ms 100
sudo ip link set can1 txqueuelen 1000
ip -details link show can1
```

Skip `up type can` if the iface is already UP (`Device or resource busy`).
Replace `can1` with whatever `ip -br` shows as the live dongle (`can0` after a
replug is common).

```bash
# Ping — this path exists. The scripts/motor path under the package does not.
python3 ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can1 --id 3

# Scan every UP bus
python3 ./scripts/scan_ids.py

# Electrical offset (shaft spins ~20 s). No Ctrl+C.
python3 ./scripts/calibrate_electrical_offset.py --channel can1 --id 3

# Visible jog around current pose
python3 ./scripts/jog_actuator.py --channel can1 --id 3
```

If jog / move need `loop-rate-limiters`, use a venv that sees apt packages:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install loop-rate-limiters
```


## Power-on order

1. STM32 **on** (solid **green** power LED). Two flashing **red** LEDs were
   seen on the Recoil boards during this lab.
2. Plug USB-C CAN dongle.
3. Bring the SocketCAN iface **UP** at 1 Mbps (`txqueuelen 1000`).
4. Ping **one** id on **that** iface.

Before unscrewing CAN: unplug USB-C **and** STM32 power.


## Hardware facts learned

### Adapters

- Four USB-C CAN dongles on a powered hub.
- Only one CAN cable went to a motor.
- The robot cable’s dongle was **`can1`** in the unplug test.
- After unplug/replug it often comes back **DOWN**.
- If only one dongle is plugged in, it may appear as **`can0`**.

### Recoil STM32 CAN pigtail colors

Two boards used **different** 3-wire color maps. Match **that board’s
silkscreen**, not a generic color code.

| Wire | Board A | Board B |
| --- | --- | --- |
| yellow | GND | CAN_H |
| green | CAN_H | CAN_L |
| black | CAN_L | GND |

Do **not** swap CANH/CANL to fix electrical-offset **rotation** direction.
That is a motor **phase** (U/V/W) issue, not CAN polarity.

### Empty bus vs live bus

When all four adapters were UP at 1 Mbps and **48 Recoil pings were offline**,
`candump` was silent. That is an **empty electrical bus**, not a Python bug.

First ACK: **`can1` id 3**.


## Error catalog

Work these in order. Do not skip to `Humanoid()`.

| Symptom | Meaning | What to do |
| --- | --- | --- |
| `No module named 'imake_humanoid_robot_lowlevel'` | Wrong cwd / no `PYTHONPATH` | `cd` to the low-level root; `export PYTHONPATH="$PWD"`; use the ping path above. |
| Pasted `import sys` into bash | Those are Python lines | Ignore; run the `python3 …` command. |
| `No module named 'can'` / PEP 668 | Ubuntu blocking pip | `sudo apt install python3-can`. Never `--break-system-packages`. |
| `Network is down` / ENETDOWN | Iface exists, **DOWN** | `sudo ip link set canX down` then `up type can bitrate 1000000`. Confirm `state UP`, qdisc not `noop`. |
| `Device or resource busy` on `up type can` | Already UP | Do not re-run `up type can`. Just ping. |
| `Motor is offline` + `Error Frame: 36` | TX, no ACK | Wiring, power, termination, wrong iface, Recoil logic power (motor DC alone is not enough). |
| Silent `candump` with adapters UP | No Recoil node on those wires | CAN pigtail, silkscreen colors, STM32 green LED. |
| `ENOBUFS` / 105 | TX queue full | `pkill` jog/move/ping; cycle iface; `txqueuelen 1000`; ping one id. |
| `Cannot find device "can1"` | USB unplugged / re-enumerated | `ip -br link show type can`. Use the name that exists. |
| `move_actuator` “Measured pos: ~3.188” and vibration | Command is ±1 rad about **0** | Use `jog_actuator.py` around the current encoder. |


## Electrical offset and phase order

### What the script does

`calibrate_electrical_offset.py` only sets Recoil `MODE_CALIBRATION` (`0x05`)
and waits ~20 s. The shaft **will spin**. The joint must be free. Do not
Ctrl+C. This is **not** `calibrate_joints.py`.

Expected motion (Berkeley flashing docs):

1. Holding torque ramps until phase current hits the target.
2. **CCW** one full mechanical turn.
3. **CW** one turn.

Lab observation on id 3: **CW first, then CCW**.

### What did **not** fix it

Writing CAN parameter `PARAM_MOTOR_PHASE_ORDER` (`0x10C`) from **+1 to −1**
and storing flash **did not** reverse the first spin.

Berkeley’s wording is: change `MOTOR_PHASE_ORDER` **in the firmware** to `-1`.
That is the Recoil `#define` in

```text
Recoil-Motor-Controller-BESC/Core/Inc/motor_controller_conf.h
```

then **reflash** with STM32CubeIDE. This repo’s
`csrc/motor_controller_conf.h` is only the **host** parameter-ID list. It has
no `#define MOTOR_PHASE_ORDER`. `set_phase_order.py` and
`configure_parameter.py` talk to the live Recoil object dictionary, not that
compile-time flag.

`scripts/motor/configure_parameter.py` has a commented example
`configure_phase_order(motor, -1)`. That is the same CAN write. It is **not**
the firmware reflash.

### Documented fixes that remain

Do **one** of the following (Berkeley flashing docs). Do **not** do both.

1. **Swap any two of the three motor phase wires** (thick U/V/W power leads).
   Not CAN. Not the encoder. Power the STM32 **off** first. Put CAN
   `phase_order` back to **+1** before the swap so you do not stack two
   reversals:

   ```bash
   python3 ./scripts/set_phase_order.py --channel can1 --id 3 --order 1
   ```

   Then power off, swap two phase leads, power on, ping, re-run electrical
   offset.

2. **Reflash Recoil** with `#define MOTOR_PHASE_ORDER -1` in firmware
   `motor_controller_conf.h`.

After a successful calib, first spin should be **CCW**, then **CW**. Then
store calibration in Recoil flash as the Recoil flashing procedure requires.


## Jog vs move

| Script | Target | Use when |
| --- | --- | --- |
| `scripts/jog_actuator.py` | Current encoder ± amplitude (default 0.5 rad, 0.2 Hz) | Bench, encoder not near 0. |
| `scripts/motor/move_actuator.py` | `sin(t)` × 1 rad about **0** | Encoder already near 0 after a good electrical + joint zero. |

Do not keep raising kp / torque if the issue is commutation direction or a
target far from the encoder.


## What not to run yet

- `Humanoid()` / `scripts/check_connection.py` / `scripts/run_locomotion.py`
  until **several** actuators ping online on **can0 and can1** (the buses
  `Humanoid()` actually opens).
- `scripts/calibrate_joints.py` (needs the full Humanoid stack and a gamepad).
- Remapping `Humanoid()` from can0/can1 onto can2/can3 until the physical
  buses are confirmed and stable.

`test_actuator_connections.py --layout berkeley` is only for the original
Berkeley leg wiring (can2 left / can3 right). iMAKE `Humanoid()` is can0/can1.


## Remaining (next hardware / calib work)

1. Confirm the live iface after every USB change (`ip -br link show type can`).
2. Put CAN `phase_order` back to **+1** if it was left at −1.
3. Swap two motor **phase** wires (or reflash firmware `MOTOR_PHASE_ORDER`).
4. Re-run electrical offset; confirm **CCW then CW**.
5. Find the next motor id on that bus (`scan_ids.py`). Repeat ping → electrical
   offset per actuator.
6. Only then bring up the second leg bus and consider `Humanoid()`.


## Upstream

- [Berkeley Humanoid Lite docs](https://berkeley-humanoid-lite.gitbook.io/docs)
- [Flashing the Motor Controllers](https://berkeley-humanoid-lite.gitbook.io/docs/getting-started-with-hardware/flashing-the-motor-controllers)
  (CCW/CW rule, phase-wire swap, firmware `MOTOR_PHASE_ORDER`)
- Recoil firmware: https://github.com/T-K-233/Recoil-Motor-Controller-BESC
