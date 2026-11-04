"""
Pins the generator-agnostic IC inspection: per-type mass from MassTable vs a Masses dataset,
the mass/count budget comparison, and every branch of the upstream-hash check.

The IC is a tiny synthetic GADGET-style HDF5 file built in tmp_path; no simulation data in git.
"""

import h5py
import numpy as np
import pytest

from amms.core.checks import Status
from amms.core.ics import (
    ExpectedComponent,
    check_mass_budget,
    check_upstream_hash,
    component_masses,
    fingerprint,
)


@pytest.fixture
def ic(tmp_path):
    """3 gas cells with per-cell Masses (like a gridded IC) + 2 halo particles via MassTable"""
    p = tmp_path / "ic.hdf5"
    with h5py.File(p, "w") as f:
        h = f.create_group("Header")
        h.attrs["NumPart_Total"] = np.array([3, 2, 0, 0, 0, 0], dtype=np.uint32)
        h.attrs["MassTable"] = np.array([0, 0.5, 0, 0, 0, 0], dtype=np.float64)
        for k, v in {"BoxSize": 0.0, "Time": 0.0, "HubbleParam": 1.0}.items():
            h.attrs[k] = v
        f.create_dataset("PartType0/Coordinates", data=np.zeros((3, 3), np.float32))
        f.create_dataset("PartType0/Masses", data=np.array([1, 2, 3], np.float32))
        f.create_dataset("PartType1/Coordinates", data=np.zeros((2, 3), np.float32))
    return p


def test_header(ic):
    h = fingerprint(ic).header
    assert h.num_part[:2] == (3, 2)
    assert not h.double_precision  # float32 Coordinates
    assert set(h.datasets) == {0, 1}  # only types that are present


def test_masses_and_budget(ic):
    fp = fingerprint(ic)
    m = component_masses(ic, fp.header)
    assert m == {0: 6.0, 1: 1.0}  # Masses summed for type 0, MassTable * N for type 1
    res = check_mass_budget(
        fp.header, m, [ExpectedComponent(0, 6.0, None), ExpectedComponent(1, 1.0, 2)]
    )
    assert all(r.status is Status.PASS for r in res)
    # n=None (gridded gas) skips the count but never the mass
    assert {r.name for r in res} == {"mass_type0", "mass_type1", "count_type1"}


def test_budget_detects_lost_gas(ic):
    # The double-shifted grid IC kept ~16% of its gas; a budget must FAIL, not pass quietly
    fp = fingerprint(ic)
    m = component_masses(ic, fp.header)
    res = check_mass_budget(fp.header, m, [ExpectedComponent(0, 6.0 / 0.16, None)])
    assert res[0].status is Status.FAIL


def test_budget_detects_count_mismatch(ic):
    fp = fingerprint(ic)
    m = component_masses(ic, fp.header)
    res = {r.name: r for r in check_mass_budget(fp.header, m, [ExpectedComponent(1, 1.0, 3)])}
    assert res["count_type1"].status is Status.FAIL
    assert (res["count_type1"].value, res["count_type1"].expected) == (2, 3)


@pytest.mark.parametrize(
    "lines, status",
    [
        (["{h}  ic.hdf5"], Status.PASS),
        (["{h}  ic.hdf5", "{o}  ic.hdf5"], Status.FAIL),  # matches only an older revision
        (["{o}  ic.hdf5"], Status.FAIL),  # changed since it was recorded
        (["{h}  other.hdf5"], Status.WARN),  # same content, recorded under another name
        (["{o}  other.hdf5", "2026-10-16 a hand-written note"], Status.WARN),  # no entry
        (["{o}  ic.hdf5", "{h}  ic.hdf5"], Status.PASS),  # last entry is authoritative
        (["{h} *ic.hdf5"], Status.PASS),  # sha256sum binary-mode marker
    ],
)
def test_upstream_hash(ic, tmp_path, lines, status):
    fp = fingerprint(ic)
    rec = tmp_path / "sha256.txt"
    rec.write_text("\n".join(lines).format(h=fp.sha256, o="0" * 64) + "\n")
    r = check_upstream_hash(fp, rec)
    assert r.status is status
    assert r.value == fp.sha256  # the file's actual hash is always what gets reported
