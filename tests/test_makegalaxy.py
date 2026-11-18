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


# --- read_vc ---------------------------------------------------------------------------
# Fixtures are written with the generator's own printf formats (makegalaxy:main.c:138-142 →
# write_header, plot_circular_speeds %f at makegalaxy:toomre.c:106-136, plot_toomre_stability
# "\n%d\n" + %g at makegalaxy:toomre.c:75-85), so the parser is pinned to what the C writes.

from amms.core.codes.makegalaxy import read_vc  # noqa: E402

R = [0.04, 0.08, 0.12]
CURVES = [[10.5, 20.25, 30.125], [1.0, 2.0, 3.0], [9.0, 18.0, 27.0], [0.5, 0.25, 0.125]]
Q_R, Q_S, Q_G = [0.0, 0.0001], [523.818, 12.5], [1e3, 6.5]


def _vc_text(*, markers=False, drop_last=False):
    out = (DATA / "dwarf.parameters").read_text()  # ends in "done\n", as write_header does
    out += f"{len(R)}\n" + "".join(f"{v:f}\n" for v in R)
    for c in CURVES:
        out += "".join(f"{v:f}\n" for v in c)
    qg = Q_G[:-1] if drop_last else Q_G
    blocks = [("list R", Q_R), ("Q", Q_S), ("Qg", qg)]
    out += f"\n{len(Q_R)}\n"
    for name, vals in blocks:
        body = "".join(f"{v:g}\n" for v in vals)
        # Himansh's MakeGalaxy_puma9 (smct1) layout, observed in ics_smc.vc lines 5036-5045, 5430-5437
        out += f"\nstarting {name}\n{body}\nending {name}\n" if markers else body
    return out


@pytest.mark.parametrize("markers", [False, True], ids=["makegalaxy", "puma9-markers"])
def test_read_vc_fields(tmp_path, markers):
    p = tmp_path / "x.vc"
    p.write_text(_vc_text(markers=markers))
    vc = read_vc(p)
    assert vc.params == read_parameters(DATA / "dwarf.parameters")  # header == .parameters
    assert vc.r.tolist() == R
    # Order is total, disk (tree), halo, bulge -- and these are v_c^2, not v_c
    assert [
        vc.vc2_total.tolist(),
        vc.vc2_disk.tolist(),
        vc.vc2_halo.tolist(),
        vc.vc2_bulge.tolist(),
    ] == CURVES
    assert vc.q_r.tolist() == Q_R
    assert vc.q_stars.tolist() == Q_S
    assert vc.q_gas.tolist() == Q_G


def test_read_vc_truncated_toomre_block_raises(tmp_path):
    p = tmp_path / "x.vc"
    p.write_text(_vc_text(drop_last=True))
    with pytest.raises(ValueError, match="Toomre block"):
        read_vc(p)


def test_read_vc_without_done_raises(tmp_path):
    p = tmp_path / "x.vc"
    p.write_text(_vc_text().replace("done\n", ""))
    with pytest.raises(ValueError, match="done"):
        read_vc(p)
