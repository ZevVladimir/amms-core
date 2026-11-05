"""
Pins the MakeGalaxy mass split (makegalaxy:structure.c:77-90) against real IC headers.

The expected values are MassTable * N read from the actual generated files, so a change to
component_budget that disagrees with what the binary wrote fails here. Fixtures are the two
.hdf5.parameters files the generator wrote back (Ethan's dwarf, Zev's smc_test).
"""

from pathlib import Path

import pytest

from amms.core.codes.makegalaxy import component_budget, read_input, read_parameters

DATA = Path(__file__).parent / "data"

# .parameters is written with %g (makegalaxy:main.c:180, write_header): 6 significant digits, e.g. M200 1.84741
# vs 1.8474050 actually used. Budgets from it are only good to ~5e-6 relative, the same reason
# ics.MASS_RTOL is 1e-5
REL = 1e-5


def budget(name):
    return {c.ptype: c for c in component_budget(read_parameters(DATA / name))}


def test_dwarf_budget_matches_stage1_ic():
    # MassTable * N from ics_dwarf_live_1e6.hdf5 (Ethan's stage-1 IC)
    b = budget("dwarf.parameters")
    assert b[0].mass == pytest.approx(1_000_000 * 5.96513565e-08, rel=REL)
    assert b[1].mass == pytest.approx(30_000_000 * 5.06792686e-08, rel=REL)
    # Stars only: MD includes the gas, so MD*M200 would be wrong here
    assert b[2].mass == pytest.approx(200_000 * 5.59674248e-08, rel=REL)
    assert b[3].mass == pytest.approx(20_000 * 3.98004727e-08, rel=REL)
    assert 5 not in b  # MBH = 0: no BH particle
    assert {p: c.n for p, c in b.items()} == {0: 1_000_000, 1: 30_000_000, 2: 200_000, 3: 20_000}


def test_smc_test_budget_matches_ic():
    # MassTable * N from ics_smc.hdf5
    b = budget("smc_test.parameters")
    assert b[0].mass == pytest.approx(522_000 * 4.95472610e-08, rel=REL)
    assert b[1].mass == pytest.approx(500_000 * 3.59135532e-06, rel=REL)
    assert b[2].mass == pytest.approx(1_044_000 * 2.47736305e-08, rel=REL)
    assert 3 not in b  # MB = 0, N_BULG = 0: dropped, not kept as an empty component
    assert b[5].n == 1  # MBH > 0 places one BH particle at the origin
    assert b[5].mass == pytest.approx(1.84740502e-08, rel=REL)


def test_budget_sums_to_m200():
    for name in ("dwarf.parameters", "smc_test.parameters"):
        params = read_parameters(DATA / name)
        total = sum(c.mass for c in component_budget(params))
        assert total == pytest.approx(params["M200"], rel=1e-12)


def test_read_parameters_stops_at_done(tmp_path):
    p = tmp_path / "x.parameters"
    p.write_text("M200  \t1.5\nMD    \t0.03\ndone\nM200\t99\n")
    assert read_parameters(p) == {"M200": 1.5, "MD": 0.03}


def test_read_input_mirrors_c_parser(tmp_path):
    # makegalaxy:read_param.c:223-226: first two whitespace tokens, '%' lines skipped, trailing junk ignored
    p = tmp_path / "in.txt"
    p.write_text("V200   40.91 #45.0  % comment\n%LAMBDA 0.038\nCC 15.0\n\nlonetoken\n")
    assert read_input(p) == {"V200": "40.91", "CC": "15.0"}
