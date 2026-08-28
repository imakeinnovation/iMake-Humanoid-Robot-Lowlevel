#!/usr/bin/env bash
# Bring up SocketCAN interfaces for the iMAKE humanoid.
# Humanoid() uses can0 (left) and can1 (right) at 1 Mbps.
# The robot PC may still have Berkeley wiring on can2/can3; those are
# brought up whenever the interfaces exist.
#
# Safe to `source` (does not exit the calling shell) or execute.

set -u

PATH="/usr/sbin:/sbin:${PATH}"
BITRATE=1000000
IFACES=(can0 can1 can2 can3)

_sourced=0
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    _sourced=1
fi

if [[ "${EUID}" -ne 0 ]]; then
    SUDO="sudo"
else
    SUDO=""
fi

if ! command -v ip >/dev/null 2>&1; then
    echo "error: the 'ip' command is not available. Install iproute2 (and can-utils)." >&2
    if [[ "${_sourced}" -eq 1 ]]; then
        return 1
    fi
    exit 1
fi

iface_exists() {
    local iface="$1"
    [[ -e "/sys/class/net/${iface}" ]] || ip link show "${iface}" >/dev/null 2>&1
}

iface_is_up() {
    local iface="$1"
    ip -o link show "${iface}" 2>/dev/null | grep -q "UP"
}

configure_can() {
    local iface="$1"
    local bitrate="$2"

    if ! iface_exists "${iface}"; then
        echo "Configuring ${iface} @ $((bitrate / 1000000)) Mbps... MISSING (interface not found)"
        return 1
    fi

    if iface_is_up "${iface}"; then
        if ! ${SUDO} ip link set "${iface}" down; then
            echo "Configuring ${iface} @ $((bitrate / 1000000)) Mbps... FAIL (could not bring interface down)"
            return 1
        fi
    fi

    echo "Running: ${SUDO} ip link set ${iface} up type can bitrate ${bitrate}"
    if ${SUDO} ip link set "${iface}" up type can bitrate "${bitrate}"; then
        echo "Configuring ${iface} @ $((bitrate / 1000000)) Mbps... OK"
        return 0
    fi

    echo "Configuring ${iface} @ $((bitrate / 1000000)) Mbps... FAIL"
    return 1
}

configured=0
failed=0

echo "iMAKE Humanoid Robot — CAN bring-up (${BITRATE} bit/s)"
echo "Interfaces: ${IFACES[*]}  (missing buses are skipped)"
echo "Using: ${SUDO:+sudo }ip   (you may be prompted for a password)"
echo

for iface in "${IFACES[@]}"; do
    if ! iface_exists "${iface}"; then
        echo "Configuring ${iface} @ $((BITRATE / 1000000)) Mbps... MISSING (interface not found)"
        continue
    fi
    if configure_can "${iface}" "${BITRATE}"; then
        configured=$((configured + 1))
    else
        failed=$((failed + 1))
    fi
done

echo
echo "Interface state:"
for iface in "${IFACES[@]}"; do
    if iface_exists "${iface}"; then
        ip -br link show "${iface}" 2>/dev/null || ip link show "${iface}"
    fi
done
echo

if [[ "${configured}" -eq 0 ]]; then
    echo "CAN bring-up failed: none of ${IFACES[*]} are present." >&2
    if [[ "${_sourced}" -eq 1 ]]; then
        return 1
    fi
    exit 1
fi
if [[ "${failed}" -ne 0 ]]; then
    echo "CAN bring-up finished with errors (${configured} up, ${failed} failed)." >&2
    if [[ "${_sourced}" -eq 1 ]]; then
        return 1
    fi
    exit 1
fi

echo "CAN bring-up complete (${configured} interface(s))."
if [[ "${_sourced}" -eq 1 ]]; then
    return 0
fi
exit 0
