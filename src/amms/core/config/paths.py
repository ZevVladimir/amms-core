"""
Resolves the cluster specific filesystem roots so paths are only hardcoded in one place: machines.yaml

detect_machine() order: AMMS_MACHINE env var -> hostname suffix match -> "local"
Doesn't use SLURM_CLUSTER_NAME which echos with nothing on puma compute
Doesn't use a raw/unmatched hostname which would cause issues on local machines which have DHCP/Tailscale churn
"""

from __future__ import annotations

import os
import socket
from functools import lru_cache
from pathlib import Path

import yaml

__all__ = ["detect_machine", "machine_root", "products_root"]

_MACHINES_FILE = Path(__file__).parent / "machines.yaml"


@lru_cache(maxsize=1)
def _machines() -> dict:
    with open(_MACHINES_FILE) as f:
        return yaml.safe_load(f)


def detect_machine() -> str:
    override = os.environ.get("AMMS_MACHINE")
    if override:
        return override

    fqdn = socket.gethostname()
    for name, cfg in _machines().items():
        suffix = cfg.get("hostname_suffix")
        if suffix and fqdn.endswith(suffix):
            return name

    return "local"


def _is_login_node(machine: str) -> bool:
    fqdn = socket.gethostname()
    patterns = _machines().get(machine, {}).get("login_hostname_patterns", [])
    return any(p in fqdn for p in patterns)


def machine_root(tier: str, machine: str | None = None) -> Path:
    """
    Looks up the machines.yaml[machine][tier]

    tier="rental" resolves to rental_login or rental_compute depending on _is_login_node

    Raises a KeyError if the tier is undefined
    """
    machine = machine or detect_machine()
    cfg = _machines()[machine]

    if tier == "rental":
        tier = "rental_login" if _is_login_node(machine) else "rental_compute"

    return Path(cfg[tier])


def products_root(machine: str | None = None) -> Path:
    return machine_root("xdisk_own", machine) / "products"
