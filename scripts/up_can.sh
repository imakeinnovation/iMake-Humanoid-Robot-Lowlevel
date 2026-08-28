#!/usr/bin/env bash
# Bring up one or more SocketCAN interfaces at 1 Mbps.
# Usage:
#   ./scripts/up_can.sh can2
#   ./scripts/up_can.sh can2 can3
# Safe to `source` (does not exit the calling shell).

set -u

PATH="/usr/sbin:/sbin:${PATH}"
BITRATE=1000000

_sourced=0
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    _sourced=1
fi

if [[ "${EUID}" -ne 0 ]]; then
    SUDO="sudo"
else
    SUDO=""
fi

ifaces=("$@")
if [[ ${#ifaces[@]} -eq 0 ]]; then
    ifaces=(can2)
fi

echo "Bringing up: ${ifaces[*]} @ ${BITRATE} bit/s"
echo "Using: ${SUDO:+sudo }ip   (you may be prompted for a password)"
echo

status=0
for iface in "${ifaces[@]}"; do
    echo "----- ${iface} before -----"
    ip link show "${iface}" || {
        echo "error: ${iface} does not exist" >&2
        status=1
        continue
    }

    echo "Running: ${SUDO} ip link set ${iface} down"
    ${SUDO} ip link set "${iface}" down || true

    echo "Running: ${SUDO} ip link set ${iface} up type can bitrate ${BITRATE}"
    if ${SUDO} ip link set "${iface}" up type can bitrate "${BITRATE}"; then
        echo "${iface}: OK"
    else
        echo "${iface}: FAIL" >&2
        status=1
    fi

    echo "----- ${iface} after -----"
    ip -details link show "${iface}" || true
    echo
done

if [[ "${_sourced}" -eq 1 ]]; then
    return "${status}"
fi
exit "${status}"
