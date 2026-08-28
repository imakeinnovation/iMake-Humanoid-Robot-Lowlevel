#!/usr/bin/env bash
# Listen and ping every SocketCAN interface that exists.
# Does not command motion. Safe to re-run after powering actuators.
#
# Usage (from source/imake_humanoid_robot_lowlevel):
#   export PYTHONPATH="$PWD"
#   ./scripts/scan_motors.sh

set -u

PATH="/usr/sbin:/sbin:${PATH}"
BITRATE=1000000
IFACES=(can0 can1 can2 can3)
IDS=(1 2)
LISTEN_SEC=2

if [[ "${EUID}" -ne 0 ]]; then
    SUDO="sudo"
else
    SUDO=""
fi

if [[ -z "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

PING_PY="./imake_humanoid_robot_lowlevel/motor/ping.py"
if [[ ! -f "${PING_PY}" ]]; then
    echo "error: run this from source/imake_humanoid_robot_lowlevel" >&2
    exit 1
fi

echo "iMAKE motor scan @ ${BITRATE} bit/s"
echo "PYTHONPATH=${PYTHONPATH}"
echo

echo "===== interfaces ====="
ip -br link show type can 2>/dev/null || ip -br link | grep -E '^can' || true
echo

for iface in "${IFACES[@]}"; do
    echo "========== ${iface} =========="
    if [[ ! -e "/sys/class/net/${iface}" ]]; then
        echo "missing"
        echo
        continue
    fi

    echo "Running: ${SUDO} ip link set ${iface} down"
    ${SUDO} ip link set "${iface}" down || true
    echo "Running: ${SUDO} ip link set ${iface} up type can bitrate ${BITRATE} restart-ms 100"
    if ! ${SUDO} ip link set "${iface}" up type can bitrate "${BITRATE}" restart-ms 100; then
        echo "${iface}: FAILED to set bitrate ${BITRATE}" >&2
        ip -details link show "${iface}" || true
        echo
        continue
    fi
    ip -details link show "${iface}" | sed -n '1,8p'
    echo

    if command -v candump >/dev/null 2>&1; then
        echo "candump ${iface} (${LISTEN_SEC}s, listen only)..."
        timeout "${LISTEN_SEC}" candump "${iface}" || true
        echo "(end candump ${iface})"
        echo
    fi

    for id in "${IDS[@]}"; do
        echo "--- ping ${iface} id ${id} ---"
        python3 "${PING_PY}" --channel "${iface}" --id "${id}" || true
        echo
    done
done

echo "Done. 'Motor is online' means that bus/id is live."
echo "Error Frame 36 (ACK) on every bus means this PC is not electrically connected to a Recoil node."
