"""
MakeGalaxy (Torrey/Cox MakeNewDisk) file formats:
    the input parameter file
    the <OutputFile>.parameters that it writes

Read-only: writing parameter files is IC *generation* and will be within amms-icgen
Prefer .parameters for derived quantities (R200, M200, RH) as that is what the binary actually computed
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from amms.core.ics import ExpectedComponent

__all__ = [
    "GAMMA",
    "G_CODE",
    "VcFile",
    "component_budget",
    "read_input",
    "read_parameters",
    "read_vc",
]

# Constants and units taken from MakeGalaxy for direct comparison
#   kpc, 1e10 Msun, km/s (makegalaxy:init.c:20-26, makegalaxy:globvars.h:8, 13-14, 22)
#   G = 6.672 not AREPO's 6.6738e-8
GAMMA = 5.0 / 3.0
G_CODE = 6.672e-8 * 1e10 * 1.989e33 / (3.085678e21 * 1e10)  # G M_u / (L_u V_u^2) = 43007.1


def read_input(path: str | os.PathLike) -> dict[str, str]:
    """
    Mirrors makegalaxy:read_param.c:223-226
        first two whitespace tokens per line
        '%' lines are skipped
        Values stay strings
        C parser decides the tag's type
    """
    out = {}
    for line in Path(path).read_text().splitlines():
        tok = line.split()
        if len(tok) >= 2 and not tok[0].startswith("%"):
            out[tok[0]] = tok[1]
    return out


def read_parameters(path: str | os.PathLike) -> dict[str, float]:
    """
    'key<TAB>value' lines from write_header() in makegalaxy:main.c:180
    Terminated by 'done'
    """
    out = {}
    for line in Path(path).read_text().splitlines():
        tok = line.split()
        if tok == ["done"]:
            break
        if len(tok) == 2:
            out[tok[0]] = float(tok[1])
    return out


def component_budget(params: dict[str, float]) -> list[ExpectedComponent]:
    """
    Mass split from makegalaxy:structure.c:77-90
    MD includes gas
    f (GasFraction) is the gas share of the disk
    The halo gets whatever is left of M200
    Takes in the output from read_parameters()
    """
    m200 = params["M200"]
    m_disk = params["MD"] * m200
    m_gas = params["f"] * m_disk
    m_stars = m_disk - m_gas
    m_bulge = params["MB"] * m200
    m_bh = params["MBH"] * m200
    m_halo = m200 - m_gas - m_stars - m_bulge - m_bh

    comps = [
        ExpectedComponent(0, m_gas, int(params["N_GAS"])),
        ExpectedComponent(1, m_halo, int(params["N_HALO"])),
        ExpectedComponent(2, m_stars, int(params["N_DISK"])),
        ExpectedComponent(3, m_bulge, int(params["N_BULG"])),
    ]
    if m_bh > 0:
        comps.append(ExpectedComponent(5, m_bh, 1))  # BH ptl at origin present when MBH>0
    return [c for c in comps if c.n]


@dataclass(frozen=True)
class VcFile:
    """
    <OutputFile>.vc (makegalaxy:main.c:129-149, makegalaxy:toomre.c:42-140)
        In MakeGalaxy units (described at top of this file)
    The generator's model for what it sampled not directly measured from the particles
    """

    params: dict[str, float]  # header == .parameters
    r: np.ndarray  # kpc, R200/1000 * i
    vc2_total: np.ndarray  # (km/s)^2, squared: R dPhi/dR in the plane
    vc2_disk: np.ndarray  # via the disk tree
    vc2_halo: np.ndarray
    vc2_bulge: np.ndarray
    q_r: np.ndarray  # kpc, log grid <= 6 Rd (makegalaxy:init.c:173); first point is R=0
    q_stars: np.ndarray  # toomre.c:65, comparable with IC
    q_gas: np.ndarray  # toomre.c:73: SH03 eff EOS sound speed, NOT the IC gas's u


def read_vc(path: str | os.PathLike) -> VcFile:
    text = Path(path).read_text()
    _, sep, body = text.partition("\ndone\n")
    if not sep:
        raise ValueError(f"{path}: no 'done' ending the header (makegalaxy:main.c:217)")
    # Following Himansh's MakeGalaxy (MakeGalaxy_puma9, smct1) which wraps the Toomre arrays in
    # 'starting list R' / 'ending Q' ... marker lines; which the makegalaxy checkout does not
    lines = [ln for ln in body.splitlines() if not ln.startswith(("starting", "ending"))]
    tok = " ".join(lines).split()  # sections are whitespace-separated; blank lines vanish
    n = int(tok[0])
    curves = np.array(tok[1 : 1 + 5 * n], dtype=float).reshape(5, n)
    rest = tok[1 : 1 + 5 * n :]
    m = int(rest[0])
    if len(rest) != 1 + 3 * m:
        raise ValueError(f"{path}: Toomre block has {len(rest) - 1} values, expected {3 * m}")
    q = np.array(rest[1:], dtype=float).reshape(3, m)
    return VcFile(read_parameters(path), *curves, *q)
