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
from datetime import date, datetime, timezone
from pathlib import Path

import h5py
import numpy as np

from amms.core.checks import CheckResult, Status
from amms.core.ids import IC_TAG_RE

__all__ = [
    "ExpectedComponent",
    "ICFingerprint",
    "ICHeader",
    "ICTag",
    "check_ic_tag",
    "check_mass_budget",
    "check_upstream_hash",
    "component_masses",
    "fingerprint",
    "read_header",
    "read_tags",
    "register_tag",
    "sha256_file",
]

_CHUNK = 8 * 1024 * 1024
_SHA256_SUM_LINE = re.compile(r"^([0-9a-f]{64})\s+\*?(\S.*)$")

_TAGS_HEADER = (
    "IC tag registry: one tag = one IC file, identified by sha256.\n"
    "Written only by amms.core.ics.register_tag. Never hand-edit, never reuse a tag:\n"
    "a regenerated IC gets the next version (e.g. edw1-edw2)"
)


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


@dataclass(frozen=True)
class ICTag:
    tag: str
    sha256: str
    path: (
        str  # where the file was when registered. Used as information since sha256 is the identity
    )
    registered: str  # ISO date


def read_tags(registry: str | os.PathLike) -> dict[str, ICTag]:
    import yaml  # keeps fingerprint() usable in venvs without pyyaml

    p = Path(registry)
    data = yaml.safe_load(p.read_text()) if p.exists() else None
    return {t: ICTag(tag=t, **v) for t, v in (data or {}).items()}


def register_tag(registry: str | os.PathLike, tag: str, ic_path: str | os.PathLike) -> ICTag:
    """
    Add a tag -> this file's sha256
    Re-registering the same tag for the same file is a no-op
    Anything making a tag or file ambiguous raises
    Read-modify-write is fine here
    """
    from amms.core._yamlio import dump_record, write_atomic

    if not IC_TAG_RE.match(tag):
        raise ValueError(f"{tag!r} is not a valid IC tag: lowercase letters then digits, e.g. edw1")
    tags = read_tags(registry)
    p = Path(ic_path).resolve()
    sha = sha256_file(p)
    if tag in tags:
        if tags[tag].sha256 == sha:
            return tags[tag]
        raise ValueError(f"tag {tag!r} already names {tags[tag].path}; tags are never reused")
    for other in tags.values():
        if other.sha256 == sha:
            raise ValueError(f"{p.name} is already registered as {other.tag!r}")
    tags[tag] = ICTag(tag, sha, str(p), date.today().isoformat())
    body = {t: {k: v for k, v in asdict(e).items() if k != "tag"} for t, e in tags.items()}
    write_atomic(Path(registry), dump_record(body, _TAGS_HEADER))
    return tags[tag]


def check_ic_tag(tag: str, ic_path: str | os.PathLike, registry: str | os.PathLike) -> CheckResult:
    """
    The IC a run will read must be the file its sim_id's tag names
    """
    tags = read_tags(registry)
    if tag not in tags:
        return CheckResult(
            "ic_tag", Status.FAIL, tag, None, f"unregistered IC tag (see {registry})"
        )
    sha = sha256_file(ic_path)
    ok = sha == tags[tag].sha256
    detail = "" if ok else f"run's IC is not the file {tag!r} names ({tags[tag].path})"
    return CheckResult("ic_tag", Status.PASS if ok else Status.FAIL, sha, tags[tag].sha256, detail)
