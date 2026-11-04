"""
MakeGalaxy (Torrey/Cox MakeNewDisk) file formats:
    the input parameter file
    the <OutputFile>.parameters that it writes

Read-only: writing parameter files is IC *generation* and will be within amms-icgen
Prefer .parameters for derived quantities (R200, M200, RH) as that is what the binary actually computed
"""

from __future__ import annotations

import os
from pathlib import Path

from amms.core.ics import ExpectedComponent

__all__ = ["component_budget", "read_input", "read_parameters"]


def read_input(path: str | os.PathLike) -> dict[str, str]:
    """
    Mirrors read_param.c MakeGalax
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
    'key<TAB>value' lines from write_header() in main.c
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
    Mass split from structure.c 77-90
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
