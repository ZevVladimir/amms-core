"""
Inspect at the file-level the IC files independent of which generator made them

Every IC is in GADGET/AREPO style HDF5 (MakeGalayx writes it and AREPO grid rewrites it) so only
need one reader. What a file *should* contain is described by codes/<generator>.py and passed as
ExpectedComponents

Hash is the identity, filename is NOT the identity.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np

from amms.core.checks import CheckResult, Status

__all__ = [
    "ExpectedComponent",
    "ICFingerprint",
    "ICHeader",
    "check_mass_budget",
    "check_upstream_hash",
    "component_masses",
    "fingerprint",
    "read_header",
    "sha256_file",
]

_CHUNK = 8 * 1024 * 1024
_SHA256_SUM_LINE = re.compile(r"^([0-9a-f]{64})\s+\*?(\S.*)$")


def sha256_file(path: str | os.PathLike) -> str:
    """
    The Whole-file sha256, streamed
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ICHeader:
    num_part: tuple[int, ...]  # per type, including the HighWord
    mass_table: tuple[float, ...]  # code units; 0 means a per-particle Masses dataset
    box_size: float  # header value only. AREPO uses the BoxSize parameter from the paramfile
    time: float
    hubble_param: float
    double_precision: bool  # from the Coordinates dtype: Flag_DoublePrecision can be stale
    datasets: dict[int, dict[str, str]]  # type -> {dataset name: dtype}


def read_header(path: str | os.PathLike) -> ICHeader:
    with h5py.File(path, "r") as f:
        a = f["Header"].attrs
        low = np.asarray(a["NumPart_Total"], dtype=np.int64)
        high = np.asarray(a.get("NumPart_Total_HighWord", np.zeros_like(low)), dtype=np.int64)
        num_part = tuple(int(n) for n in low + (high << 32))
        datasets = {
            t: {name: str(ds.dtype) for name, ds in f[f"PartType{t}"].items()}
            for t in range(len(num_part))
            if f"PartType{t}" in f
        }
        coord_dtypes = {d["Coordinates"] for d in datasets.values() if "Coordinates" in d}
        return ICHeader(
            num_part=num_part,
            mass_table=tuple(float(m) for m in a["MassTable"]),
            box_size=float(a["BoxSize"]),
            time=float(a["Time"]),
            hubble_param=float(a.get("HubbleParam", np.nan)),
            double_precision=coord_dtypes == {"float64"},
            datasets=datasets,
        )


@dataclass(frozen=True)
class ICFingerprint:
    name: str
    path: str  # Resolved path when hashed. Not used for identity (use sha256 instead)
    size_bytes: int
    sha256: str
    mtime: str  # ISO 8601, UTC
    hashed_at: str  # ISO 8601, UTC
    header: ICHeader

    def to_dict(self) -> dict:
        return asdict(self)


def fingerprint(path: str | os.PathLike) -> ICFingerprint:
    p = Path(path).resolve()
    st = p.stat()
    return ICFingerprint(
        name=p.name,
        path=str(p),
        size_bytes=st.st_size,
        sha256=sha256_file(p),
        mtime=datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        hashed_at=datetime.now(timezone.utc).isoformat(),
        header=read_header(p),
    )


def check_upstream_hash(fp: ICFingerprint, record: str | os.PathLike) -> CheckResult:
    """
    Compare against a sha256sum-style record ('HASH NAME' lines, ignoring other lines like hand written notes).
    If a name is recorded multiple times only use the LAST entry
    """
    by_name: dict[str, list[str]] = {}
    for line in Path(record).read_text().splitlines():
        m = _SHA256_SUM_LINE.match(line.strip())
        if m:
            by_name.setdefault(Path(m[2]).name, []).append(m[1])

    name = "upstream_hash"
    hashes = by_name.get(fp.name, [])
    if hashes and hashes[-1] == fp.sha256:
        return CheckResult(name, Status.PASS, fp.sha256, hashes[-1])
    if fp.sha256 in hashes:
        return CheckResult(
            name, Status.FAIL, fp.sha256, hashes[-1], "matches an OLDER recorded revision"
        )
    if any(fp.sha256 in hs for hs in by_name.values()):
        return CheckResult(
            name, Status.WARN, fp.sha256, None, "content recorded under different file name"
        )
    if hashes:
        return CheckResult(
            name, Status.FAIL, fp.sha256, hashes[-1], "file changed since it was recorded"
        )
    return CheckResult(name, Status.WARN, fp.sha256, None, f"no entry for {fp.name} in {record}")


@dataclass(frozen=True)
class ExpectedComponent:
    """What a generator says a one particle type should contain"""

    ptype: int
    mass: float  # code units
    n: int | None  # If None is used then don't check the count


def component_masses(path: str | os.PathLike, header: ICHeader) -> dict[int, float]:
    """Calculate the total mass per type: MassTable * N, or the sum of Masses when MassTable is 0"""
    out: dict[int, float] = {}
    with h5py.File(path, "r") as f:
        for t, n in enumerate(header.num_part):
            if n == 0:
                continue
            if header.mass_table[t] > 0:
                out[t] = header.mass_table[t] * n
            else:
                out[t] = float(f[f"PartType{t}/Masses"][...].astype(np.float64).sum())
    return out


# Per-particle masses get stored as float32 when there is no MassTable entry
# Generator uses doubles. Use tolerance of 1e-5 for float32 while still catching real errors
MASS_RTOL = 1e-5


def check_mass_budget(
    header: ICHeader,
    masses: dict[int, float],
    expected: list[ExpectedComponent],
    rtol: float = MASS_RTOL,
) -> list[CheckResult]:
    results = []
    for e in expected:
        got = masses.get(e.ptype, 0.0)
        ok = np.isclose(got, e.mass, rtol=rtol, atol=0.0)
        results.append(
            CheckResult(f"mass_type{e.ptype}", Status.PASS if ok else Status.FAIL, got, e.mass)
        )
        if e.n is not None:
            n = header.num_part[e.ptype]
            results.append(
                CheckResult(
                    f"count_type{e.ptype}", Status.PASS if n == e.n else Status.FAIL, n, e.n
                )
            )
    return results
