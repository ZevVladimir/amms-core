#!/usr/bin/env bash
# Creates or refreshes the AMMS venv
#
#   ./env/bootstrap.sh
#   AMMS_VENV=~/.venvs/amms-test ./env/bootstrap.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${AMMS_VENV:-$HOME/.venvs/amms}"
MIN_PY="3.10"

# Mirror detection order in amms.core.config.paths (can't import it since it runs first)
detect_machine() {
    [[ -n "${AMMS_MACHINE:-}" ]] && { echo "$AMMS_MACHINE"; return; }
    [[ -n "${SLURM_CLUSTER_NAME:-}" ]] && { echo "$SLURM_CLUSTER_NAME"; return; }
    case "$(hostname -f 2>/dev/null || hostname)" in
        *puma*) echo puma ;;
        *lynx*) echo lynx ;;
        *.hpc.arizona.edu) echo uahpc-unknown ;;
        # Don't fall back to raw hostname. DHCP names for laptops/desktops change making the lock files useless
        *)  echo local ;;
    esac
}
CLUSTER="$(detect_machine)"

# --- Load the modules ---
if ! command -v module >/dev/null 2>&1; then
    for init in "${LMOD_PKG:-/opt/ohpc/admin/lmod/lmod}/init/bash" \
            /etc/profile.d/modules.sh /etc/profile.d/lmod.sh; do
        [[ -r "$init" ]] && source "$init" &&  break
    done
fi

if command -v module >/dev/null 2>&1; then
    mapfile -t MODULES < <(grep -vE '^\s*(#|$)' "$REPO_ROOT/env/modules.txt")
    module purge
    printf 'loading modules: %s\n' "${MODULES[*]}"
    module load "${MODULES[@]}"
else
    echo "note: no 'module' command found -- assuming local machine." >&2
fi

# --- Refuse build if wrong python ---
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [[ "$(printf '%s\n%s\n' "$MIN_PY" "$PY_VER" | sort -V | head -1)" != "$MIN_PY" ]]; then
    echo "ERROR: python3 is $PY_VER but amms-core requires >= $MIN_PY." >&2
    echo "  UA's default python is 3.6.8 -- module load likely failed." >&2
    echo "  Check: module avail python / which python3" >&2
    exit 1
fi

# --- Refuse build if ensurepip is not installed ---
# done primarily for local machine
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
    echo "ERROR: this python3 has no ensurepip, so 'python3 -m venv' can't create a venv." >&2
    echo "  On Debian/Ubuntu: sudo apt install python3-venv python3-pip" >&2
    echo "  Should not be an issue on the cluster as module provides both" >&2
    exit 1
fi

echo "using python $PY_VER from $(command -v python3)"

# --- venv and editable install ---
python3 -m venv --upgrade-deps "$VENV"
source "$VENV/bin/activate"
pip install -e "${REPO_ROOT}[dev]"
pre-commit install --install-hooks || echo "note: pre-commit hooks not installed (no git repo?)" >&2

# --- record what got installed ---
# lock per (cluster, python) pair since python differs between clusters
CLUSTER="${SLURM_CLUSTER_NAME:-$(hostname -s)}"
mkdir -p "$REPO_ROOT/env/locks"
LOCK="$REPO_ROOT/env/locks/${CLUSTER}-py${PY_VER}.txt"
pip freeze --exclude-editable > "$LOCK"
echo "wrote lock: ${LOCK#"$REPO_ROOT"/}"

cat <<EOF
done. In every new shell, and at the top of every job script:

    source $REPO_ROOT/env/activate.sh

EOF
