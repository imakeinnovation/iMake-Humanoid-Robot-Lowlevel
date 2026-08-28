#!/usr/bin/env bash
# Install python-can without breaking Ubuntu's externally-managed Python.
# Prefers apt (so system python3 can import can). Falls back to a local venv.
# Safe to re-run. Does not command motion or open CAN.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV="${ROOT}/.venv"

if python3 -c "import can" >/dev/null 2>&1; then
    python3 -c "import can; print('python-can already available:', can.__file__)"
    exit 0
fi

echo "system python3 cannot import can (PEP 668 / externally-managed-environment is expected)."
echo "Installing python3-can via apt so 'python3' can import it..."

if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get install -y python3-can python3-venv python3-full python3-pip
    if python3 -c "import can" >/dev/null 2>&1; then
        python3 -c "import can; print('python-can OK (system):', can.__file__)"
        exit 0
    fi
    echo "apt python3-can did not make 'import can' work. Creating ${VENV}..."
else
    echo "apt-get not found. Creating ${VENV}..."
fi

if [[ ! -x "${VENV}/bin/python" ]]; then
    python3 -m venv "${VENV}"
fi

"${VENV}/bin/python" -m pip install --upgrade pip
"${VENV}/bin/python" -m pip install python-can
"${VENV}/bin/python" -c "import can; print('python-can OK (venv):', can.__file__)"

echo
echo "Use the venv python for ping, not system python3:"
echo "  source ${VENV}/bin/activate"
echo "  export PYTHONPATH=\"${ROOT}\""
echo "  python ./imake_humanoid_robot_lowlevel/motor/ping.py --channel can2 --id 1"
