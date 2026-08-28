#!/usr/bin/env bash
# Bring down SocketCAN interfaces that exist. Safe to run when some buses are absent.
# Safe to `source` (does not exit the calling shell) or execute.

set -u

PATH="/usr/sbin:/sbin:${PATH}"
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

status=0

for iface in "${IFACES[@]}"; do
    if ! iface_exists "${iface}"; then
        echo "Stopping ${iface}... MISSING (interface not found)"
        continue
    fi
    if ${SUDO} ip link set "${iface}" down; then
        echo "Stopping ${iface}... OK"
    else
        echo "Stopping ${iface}... FAIL"
        status=1
    fi
done

if [[ "${_sourced}" -eq 1 ]]; then
    return "${status}"
fi
exit "${status}"
