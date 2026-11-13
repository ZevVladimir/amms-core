"""
AREPO output-file formats for this build (Arepo2-smuggle-mod d323be6 + puma buildsystem):
<paramfile>-usedvalues, sfr.txt, cpu.txt, build/arepoconfig.h, generated from Config.sh by the build (arepo-smuggle:Makefile:62-65)

Parsing only. Parameter truth comes from -usedvalues to avoid hard coding units
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

__all__ = [
    "CpuBlock",
    "CpuTimer",
    "SfrLog",
    "Units",
    "read_config",
    "read_cpu",
    "read_sfr",
    "read_usedvalues",
]

# AREPO's values (arepo-smuggle:src/data/constants.h:138,166)
SOLAR_MASS_G = 1.989e33
SEC_PER_MYR = 3.15576e13


def _final_pass(t: np.ndarray) -> np.ndarray:
    """
    Mask keeping only the last pass over each time range
    Restart resumes from its restart file's time but keeps appending to the output file
    A row only survives if its time is earlier than every later row's
    """
    return t < np.append(np.minimum.accumulate(t[::-1])[::-1][1:], np.inf)


def read_usedvalues(path: str | os.PathLike) -> dict[str, str]:
    """
    '<Tag> <value>' lines (from arepo-smuggle:src/io/parameters.cc:125-145): every parameter that AREPO resolved (includes defaults)
    Values are kept as strings
    Limitation: Values with spaces only keep first word (this isn't expected)
    """
    out = {}
    for line in Path(path).read_text().splitlines():
        tok = line.split()
        if len(tok) >= 2 and not tok[0].startswith(("%", "#")):
            out[tok[0]] = tok[1]
    return out


def read_config(path: str | os.PathLike) -> dict[str, str | None]:
    """
    build/arepoconfig.h, generated from Config.sh by the build (arepo-smuggle:Makefile:62-65) '#define NAME [value]' -> {NAME: value or None}. Describes what
    the binary was built with
    """
    out = {}
    for line in Path(path).read_text().splitlines():
        m = re.match(r"#define\s+(\S+)(?:\s+(\S+))?", line)
        # prepare-config.py wraps the defines in an include guard but it is not a build option
        if m and m[1] != "AREPOCONFIG_H":
            out[m[1]] = m[2]
    return out


@dataclass(frozen=True)
class Units:
    """
    Code -> physical conversions from the run's own parameters
    GADGET/AREPO units carry h:
        length:     kpc/h
        mass:       1e10 Msun/h
        time:       (kpc/h)/(km/s)
    My ICs use h=1 but kept in case this changes
    """

    length_cm: float
    mass_g: float
    velocity_cm_s: float
    hubble: float

    @classmethod
    def from_usedvalues(cls, params: dict[str, str]) -> Units:
        return cls(
            length_cm=float(params["UnitLength_in_cm"]),
            mass_g=float(params["UnitMass_in_g"]),
            velocity_cm_s=float(params["UnitVelocity_in_cm_per_s"]),
            hubble=float(params["HubbleParam"]),
        )

    @property
    def time_myr(self) -> float:
        return self.length_cm / self.velocity_cm_s / self.hubble / SEC_PER_MYR

    @property
    def mass_msun(self) -> float:
        return self.mass_g / self.hubble / SOLAR_MASS_G

    @property
    def time_gyr(self) -> float:
        return self.time_myr / 1e3


@dataclass(frozen=True)
class SfrLog:
    """
    sfr.txt columns (arepo-smuggle:src/cooling_sfr/starformation.cc:646)
    Use code units except two rates
    """

    time: np.ndarray  # All.Time
    mass_expected: np.ndarray  # total_sm: stellar mass expected to form at this step
    sfr: np.ndarray  # totsfrrate, Msun/yr: instantaneous total SFR of the gas
    sfr_realised: (
        np.ndarray
    )  # rate_in_msunperyear, Msun/yr: what the stochastic spawning actually made
    mass_formed_step: np.ndarray  # total_sum_mass_stars: formed this step
    mass_formed_cum: np.ndarray  # mass_formed_cum: rebuilt as cumsum(mass_formed_step); upstream cum_mass_stars resets on restart
    rows_dropped: int  # rows superseded by a restart (see read_sfr() below)


def read_sfr(path: str | os.PathLike) -> SfrLog:
    """
    a restart resumes from its restart file's time but keeps appending to sfr.txt
    So lines the first pass wrote after that time remain
    Keep only the final pass: a row survives if its time is earlier than every later row's
    """
    d = np.loadtxt(path, ndmin=2)
    t = d[:, 0]
    keep = _final_pass(t)
    d = d[keep]
    # cum_mass_stars is a file-static reset to 0 on every (re)start
    # (arepo-smuggle:src/cooling_sfr/starformation.cc:47), not a restart state
    # Column 6 starts counting from the last start. Rebuild it using the per-step mass of the kept rows
    d[:, 5] = np.cumsum(d[:, 4])
    return SfrLog(*(d[:, i] for i in range(6)), rows_dropped=int((~keep).sum()))


@dataclass(frozen=True)
class CpuTimer:
    depth: int  # nesting level; children follow their parent
    name: str
    cumulative_s: float
    cumulative_pct: float


@dataclass(frozen=True)
class CpuBlock:
    step: int
    time: float  # kept in code units
    ntask: int
    timers: list[CpuTimer]

    @property
    def total_s(self) -> float:
        return next(t.cumulative_s for t in self.timers if t.name == "total")


def read_cpu(path: str | os.PathLike) -> CpuBlock:
    """
    The last 'Step ...' block of cpu.txt (arepo-smuggle:src/logs/logs.cc:919-926): per timer
    The indented name and then (diff, diff%, max, cumulative, cumulative%)
    Parse from the right: name can contain spaces but numbers do not
    Indentation is 2 spaces each level
    """
    text = Path(path).read_text()
    heads = list(re.finditer(r"^Step (\d+), Time: (\S+), CPUs: (\d+)", text, re.M))
    if not heads:
        raise ValueError(f"no 'Step' block in {path}")
    m = heads[-1]
    timers = []
    for line in text[m.end() :].splitlines()[1:]:
        if not line.strip():
            break  # blank lines end the blocks
        tok = line.split()
        if len(tok) < 6:
            continue  # the 'diff max cumulative' column header
        depth = (len(line) - len(line.lstrip())) // 2
        timers.append(
            CpuTimer(depth, " ".join(tok[:-5]), float(tok[-2]), float(tok[-1].rstrip("%")))
        )
    return CpuBlock(int(m[1]), float(m[2]), int(m[3]), timers)


@dataclass(frozen=True)
class EnergyLog:
    """
    Read in energy.txt (arepo-smuggle:src/logs/global.cc:91), written in code units with
    one row per TimeBetStatistics
    Columns 1-3 (totals) are dropped since they are the per-type sums
    Per-type arrays are (n_rows, 6), and are indexed by PartType
    """

    time: np.ndarray
    e_int: np.ndarray
    e_pot: np.ndarray  # all 0 unless built with EVALPOTENTIAL (global.cc:267)
    e_kin: np.ndarray
    mass: np.ndarray
    egy_injection: np.ndarray  # All.EgyInjection
    rows_dropped: int

    @property
    def has_potential(self) -> bool:
        # Unless the potential is saved can't make an energy conservation statement
        return bool(self.e_pot.any())


def read_energy(path: str | os.PathLike) -> EnergyLog:
    d = np.loadtxt(path, ndmin=2)
    if d.shape[1] != 30:
        # Column count is fixed by a fprintf
        # Anything else is a different AREPO version
        raise ValueError(f"{path}: {d.shape[1]} columns, expected 30 (global.cc:91)")
    keep = _final_pass(d[:, 0])
    d = d[keep]
    per = d[:, 4:22].reshape(-1, 6, 3)  # (row, type, [int, pot, kin])
    return EnergyLog(
        d[:, 0],
        per[..., 0],
        per[..., 1],
        per[..., 2],
        d[:, 22:28],
        d[:, 28],
        rows_dropped=int((~keep).sum()),
    )


@dataclass(frozen=True)
class MemoryPeak:
    total_mb: float  # inclues generic comm buffers: ~MaxMemSize by construction so not useful as a basis to judge memory usage
    without_generic_mb: float  # real per-task requirement


_MEM = re.compile(
    r"^MEMORY:\s+Largest Allocation = (\S+) Mbyte\s+\|\s+"
    r"Largest Allocation Without Generic = (\S+) Mbyte",
    re.M,
)


def read_memory_peak(path: str | os.PathLike) -> MemoryPeak:
    """
    Max-over-tasks high-water from memory.txt (arepo-smuggle:src/data/mymalloc.cc:356)
    Blocks are written only when either mark grows >=5% (mymalloc.cc:411,422) so the reported
    peak is within 5% of the actual value
    """
    hits = _MEM.findall(Path(path).read_text())
    if not hits:
        raise ValueError(f"no 'MEMORY:' line in {path}")
    a = np.array(hits, dtype=float)
    return MemoryPeak(float(a[:, 0].max()), float(a[:, 1].max()))


@dataclass(frozen=True)
class TimebinLog:
    """
    Done per sync-point: the smallest occupied timestep bin (in code units)
    """

    time: np.ndarray
    min_bin: np.ndarray
    min_dt: np.ndarray
    n_grav: np.ndarray  # number of particles in a bin
    n_hydro: np.ndarray  # number of gas cells in a bin
    rows_dropped: int


_SYNC = re.compile(r"^Sync-Point \d+, Time: ([^,\s]+),")
_BIN = re.compile(r"^ [X ]  bin=\s*(\d+)\s+(.*)$")


# def read_timebins(path: str | os.PathLike) -> TimebinLog:
#     """
#     Block header from arepo-smuggle:src/logs/logs.cc:549
#     bin lines from logs.cc:679
#     Only occupied bins are pritned
#     Bin 0 (from step 0 only) has dt=0
#     """
#     rows, cur, idt = [], None, None
#     with open(path) as f:
#         for line in f:
#             if m := _SYNC.match(line):
#                 if cur is not None:
#                     rows.append(cur)
#                 cur = [float(m[1]), np.inf, np.nan, 0, 0]
#             elif line.startswith("Occupied timebins:"):
#                 # names after 'Occupied timebins:'; bin lines have the same order after 'bin=NN'
#                 idt = line.split()[2:].index("dt")
