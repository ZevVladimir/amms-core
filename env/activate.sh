# Load in the pinned modules as described in modules.txt
# Activate the venv
# 
# TO USE: `source ~/amms-core/env/activate.sh`

_amms_repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v module >/dev/null 2>&1; then
    module purge
    module load $(grep -vE '^\s*(#|$)' "$_amms_repo/env/modules.txt" | tr '\n' ' ')
fi

source "${AMMS_VENV:-$HOME/.venvs/amms}/bin/activate"
unset _amms_repo
