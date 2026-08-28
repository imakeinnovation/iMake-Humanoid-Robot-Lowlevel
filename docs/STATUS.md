# Robot status report — 2026-08-27

**Host:** `imakeinnovationcnter@iMakeHumanoid`
**Tree:** `~/iMake-Humanoid-Robot` (copy this session’s low-level tree onto the PC if scripts are missing)
**Operator log:** [BRINGUP.md](BRINGUP.md)

This is a status snapshot, not a how-to. Commands and error catalog are in BRINGUP.md.


## Bottom line

The robot is **not walkable**. Software can talk to SocketCAN. **One** Recoil actuator has answered ping (**can1 id 3**). Electrical offset on that motor **ran in the wrong first direction**. The rest of the biped is electrically offline or not plugged in. Do **not** start `Humanoid()`, joint calibration, or RL.


## What is working

| Area | State |
| --- | --- |
| Robot PC Python | System `python3` + `apt` `python3-can` / `python3-numpy`. Package imports with `PYTHONPATH`. |
| SocketCAN stack | `gs_usb` at 1 Mbps. Bring-up scripts, ping, ACK/DOWN error decode. |
| First Recoil | **can1 id 3** → `Motor is online`. |
| Electrical offset command | Recoil `MODE_CALIBRATION` ran ~20 s on that id. Shaft did spin. |
| Bench jog path | `jog_actuator.py` around current encoder, kp=20, kd=2, torque=4 (script in this tree). |
| Gamepad / sim paths in this snapshot | Linux stick calibration and asset-path loads were fixed earlier; unused until the robot is on CAN. |


## What is not working / not done

| Area | State |
| --- | --- |
| Rest of the biped | Ids 1, 2, 4–8, 11–14 on the live bus were **offline**. Only one CAN cable was on a motor. |
| USB-CAN names | **Unstable.** Four dongles on a hub. After unplug/replug the live iface is often **DOWN** and may show up as **can0**, not can1. |
| Electrical offset direction | First spin **CW then CCW**. Docs require **CCW then CW**. |
| CAN `phase_order` +1 → −1 | **Did not** reverse the first spin. That is not the firmware `#define`. |
| Closed-loop about 0 | `move_actuator.py` targets ±1 rad about **0** while encoder sat ~**3.19 rad** → vibration, little motion. |
| `Humanoid()` | Still opens **can0 / can1**. Not safe until several actuators ping on those buses. |
| Joint zeros / IMU / RL | Not started. |


## Hardware as last seen

- STM32 Recoil: solid **green** power LED, two flashing **red** LEDs.
- Two boards used **different** CAN wire colors. Match the silkscreen, not a generic code.
- Empty `candump` + Error Frame **36** means this PC transmitted and nobody ACKed (wiring/power), not a Python bug.


## What else needs to happen

Do this **in order**. Do not skip to locomotion.

### 1. Freeze the live CAN name

After every USB change:

```bash
ip -br link show type can
```

Bring that iface UP at 1 Mbps, `txqueuelen 1000`, ping **one** id. If only one dongle is plugged in, treat it as **can0** until proven otherwise.

### 2. Finish actuator 3 (the only live motor)

1. If CAN `phase_order` was left at −1, write it back to **+1** and store flash.
2. Power STM32 **off**. Swap **any two** of the three motor **phase** wires (U/V/W). Not CAN. Not encoder.
3. Power on, ping the same id on the iface that exists.
4. Re-run electrical offset. First turn must be **CCW**, then **CW**. No Ctrl+C.
5. Confirm a slow jog around the **current** encoder (`jog_actuator.py`). Do not use `move_actuator.py` until the encoder is near 0.

Alternative to the wire swap: reflash Recoil with `#define MOTOR_PHASE_ORDER -1` (STM32CubeIDE). Do **not** do both.

### 3. Bring up the rest of one leg

Plug **one** more actuator at a time (power, CAN daisy-chain, silkscreen). For each:

1. Find the id (`scan_ids.py` on the live iface).
2. Ping until `Motor is online`.
3. Electrical offset (CCW first). Fix phase wires per motor if CW first.
4. Jog around current pose.

Left-leg ids (iMAKE / `Humanoid()`): **1, 3, 5, 7, 11, 13** on **can0**.
Right-leg ids: **2, 4, 6, 8, 12, 14** on **can1**.

Today only **id 3** answered, and it was on **can1** because that was the only cable. When the robot is fully wired, id 3 belongs on the **left** bus (**can0**) as `left_hip_yaw`. Do not remap `Humanoid()` to chase a bench dongle name.

### 4. Second leg bus

Repeat ping → electrical offset → jog for the other six actuators on the other USB-CAN. Confirm both ifaces stay UP after replug.

### 5. Only then: robot software stack

When **12** biped actuators ping online on **can0 and can1**:

1. `scripts/test_actuator_connections.py` (layout `imake`) exit 0.
2. `calibrate_joints.py` (move to mechanical limits, **B** / `q`).
3. IMU + gamepad via `check_connection.py` / `test_joystick.py`.
4. Damping / idle, then RL init (`LB`+`A`) and RL run (`RB`+`A`).

Do **not** change Recoil ping payload `0xCA`, actuator IDs, joint order, RL gains in `Humanoid()`, or IMU transforms.


## Explicitly out of scope until step 5

- `Humanoid()`, `check_connection.py`, `run_locomotion.py`, `make run`
- Raising kp/torque to “make it move” while commutation direction is wrong
- Swapping CANH/CANL to fix rotation direction
- Pip onto system Python / `--break-system-packages`
- Assuming `can1` is still the live dongle after a cable change
