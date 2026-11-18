"""
Pins the AREPO output-file parsers in amms.core.codes.arepo against the formats this build writes.

Fixtures are generated with the upstream printf formats rather than typed by hand, so a test
checks the parser against what AREPO emits, not against my reading of it:
    sfr.txt          arepo-smuggle:src/cooling_sfr/starformation.cc:646
    cpu.txt          arepo-smuggle:src/logs/logs.cc:919-926
    -usedvalues      arepo-smuggle:src/io/parameters.cc:124-145 (MAXLEN_PARAM_TAG 50, reals as %g)
    arepoconfig.h    arepo-smuggle:buildsystem/prepare-config.py:55-62,95
    energy.txt       arepo-smuggle:src/logs/global.cc:91
    timebins.txt     arepo-smuggle:src/logs/logs.cc:549,631,679
    memory.txt       arepo-smuggle:src/data/mymalloc.cc:356 (+ decoy memorymanager.cc:151)
Values in the energy/timebins/memory fixtures are smc_001_edw1_sh03's own log lines.
"""

import numpy as np
import pytest

from amms.core.codes import arepo

SFR_FMT = "%14e %14e %14e %14e %14e %14e\n"
TAG_W = 50  # MAXLEN_PARAM_TAG, arepo-smuggle:src/io/parameters.h:29


def write_sfr(path, times):
    # Column 5 (mass formed this step) is set to the row's position in the file, so a test can tell
    # which pass a surviving row came from and that all columns were trimmed together
    path.write_text(
        "".join(SFR_FMT % (t, 0.0, 0.1, 0.1, float(i), 0.0) for i, t in enumerate(times))
    )
    return path


def test_sfr_no_restart_keeps_every_row(tmp_path):
    s = arepo.read_sfr(write_sfr(tmp_path / "sfr.txt", [0.0, 1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(s.time, [0.0, 1.0, 2.0, 3.0])
    assert s.rows_dropped == 0


def test_sfr_restart_drops_rows_superseded_by_later_pass(tmp_path):
    # First pass reaches t=4, restart file was at t=2, second pass resumes and appends 2.5, 3.5, 5
    s = arepo.read_sfr(write_sfr(tmp_path / "sfr.txt", [0, 1, 2, 3, 4, 2.5, 3.5, 5]))
    np.testing.assert_array_equal(s.time, [0, 1, 2, 2.5, 3.5, 5])
    np.testing.assert_array_equal(s.mass_formed_step, [0, 1, 2, 5, 6, 7])
    assert s.rows_dropped == 2


def test_sfr_restart_row_at_same_time_keeps_later_pass(tmp_path):
    # Second pass re-logs t=2 exactly: the strict '<' must keep the second write, not both
    s = arepo.read_sfr(write_sfr(tmp_path / "sfr.txt", [0, 1, 2, 3, 2, 3, 4]))
    np.testing.assert_array_equal(s.time, [0, 1, 2, 3, 4])
    np.testing.assert_array_equal(s.mass_formed_step, [0, 1, 4, 5, 6])
    assert s.rows_dropped == 2


def test_sfr_running_total_continuous_across_restart(tmp_path):
    # cum_mass_stars is a file-static that restarts at 0 (arepo-smuggle:src/cooling_sfr/starformation.cc:47),
    # so the raw column 6 drops back after the restart at t=2. The returned total must not
    rows = [  # (time, mass formed this step, raw column 6 as AREPO writes it)
        (0, 1, 1),
        (1, 1, 2),
        (2, 1, 3),
        (3, 1, 4),  # superseded
        (2.5, 2, 2),  # second pass: raw total restarted from 0
        (3.5, 2, 4),
    ]
    path = tmp_path / "sfr.txt"
    path.write_text("".join(SFR_FMT % (t, 0.0, 0.1, 0.1, m, c) for t, m, c in rows))
    s = arepo.read_sfr(path)
    np.testing.assert_array_equal(s.mass_formed_cum, [1, 2, 3, 5, 7])


def test_sfr_single_row(tmp_path):
    s = arepo.read_sfr(write_sfr(tmp_path / "sfr.txt", [0.0]))
    assert s.time.shape == (1,)
    assert s.rows_dropped == 0


def write_usedvalues(path, params):
    lines = []
    for tag, val in params.items():
        fmt = "%g" if isinstance(val, float) else "%d" if isinstance(val, int) else "%s"
        lines.append(f"%-{TAG_W}s{fmt}\n" % (tag, val))
    path.write_text("".join(lines))
    return path


UNITS_KPC_1E10_KMS = {
    "UnitLength_in_cm": 3.085678e21,
    "UnitMass_in_g": 1.989e43,
    "UnitVelocity_in_cm_per_s": 1e5,
}


def test_units_known_answer_h1(tmp_path):
    # kpc / (km/s) = 0.9778 Gyr. Values pass through %g on the way out of AREPO (3.085678e21 ->
    # 3.08568e+21), which is ~5e-7 relative and inside the tolerance
    p = arepo.read_usedvalues(
        write_usedvalues(tmp_path / "u", {**UNITS_KPC_1E10_KMS, "HubbleParam": 1.0})
    )
    u = arepo.Units.from_usedvalues(p)
    assert u.time_myr == pytest.approx(977.79, rel=1e-4)
    assert u.mass_msun == pytest.approx(1e10, rel=1e-6)


def test_units_divide_by_h(tmp_path):
    p = arepo.read_usedvalues(
        write_usedvalues(tmp_path / "u", {**UNITS_KPC_1E10_KMS, "HubbleParam": 0.7})
    )
    u = arepo.Units.from_usedvalues(p)
    assert u.time_myr == pytest.approx(977.79 / 0.7, rel=1e-4)
    assert u.mass_msun == pytest.approx(1e10 / 0.7, rel=1e-6)


def test_usedvalues_keeps_strings_and_skips_comments(tmp_path):
    path = write_usedvalues(
        tmp_path / "param.txt-usedvalues",
        {"OutputDir": "./output/", "TimeMax": 1.0, "MaxMemSize": 9000},
    )
    path.write_text("% comment\n# comment\n\n" + path.read_text())
    assert arepo.read_usedvalues(path) == {
        "OutputDir": "./output/",
        "TimeMax": "1",  # %g of 1.0
        "MaxMemSize": "9000",
    }


def test_config_flags_and_values(tmp_path):
    # prepare-config.py wraps the defines in an include guard and writes flags as '#define NAME '
    # (trailing space). The guard is not a build option and must not appear in the result
    path = tmp_path / "arepoconfig.h"
    path.write_text(
        "#ifndef AREPOCONFIG_H\n"
        "#define AREPOCONFIG_H\n"
        "#define NTYPES 6\n"
        "#define VORONOI \n"
        "#define DOUBLEPRECISION 1\n"
        "#endif\n"
    )
    assert arepo.read_config(path) == {"NTYPES": "6", "VORONOI": None, "DOUBLEPRECISION": "1"}


CPU_HEADER = "                          diff            max          cumulative\n"
CPU_LINE = "%*s%-*s%10.2f  %5.1f%% %6.2f %10.2f  %*s%5.1f%%\n"


def cpu_block(step, time, ntask, timers):
    """timers: (depth, name, cumulative_s, cumulative_pct); per-step columns are filler"""
    out = f"Step {step}, Time: {time:g}, CPUs: {ntask}, MultiDomains: 8, HighestActiveTimeBin: 20\n"
    out += CPU_HEADER
    for depth, name, cum, pct in timers:
        out += CPU_LINE % (
            2 * depth,
            "",
            20 - 2 * depth,
            name,
            1.0,
            10.0,
            1.0,
            cum,
            5 * depth,
            "",
            pct,
        )
    return out + "\n"


def test_cpu_returns_last_block_with_nesting(tmp_path):
    path = tmp_path / "cpu.txt"
    path.write_text(
        cpu_block(1, 0.001, 94, [(0, "total", 10.0, 100.0), (1, "treegrav", 5.0, 50.0)])
        + cpu_block(
            28727,
            1.02,
            94,
            [
                (0, "total", 73800.0, 100.0),
                (1, "treegrav", 42804.0, 58.0),
                (2, "treebuild", 3690.0, 5.0),
                (1, "two words", 11808.0, 16.0),  # parser claims names may contain spaces
            ],
        )
    )
    b = arepo.read_cpu(path)
    assert (b.step, b.time, b.ntask) == (28727, 1.02, 94)
    assert [(t.depth, t.name) for t in b.timers] == [
        (0, "total"),
        (1, "treegrav"),
        (2, "treebuild"),
        (1, "two words"),
    ]
    assert b.timers[1].cumulative_s == 42804.0
    assert b.timers[1].cumulative_pct == 58.0
    assert b.total_s == 73800.0


def test_cpu_without_step_block_raises(tmp_path):
    path = tmp_path / "cpu.txt"
    path.write_text("not a cpu log\n")
    with pytest.raises(ValueError, match="no 'Step' block"):
        arepo.read_cpu(path)


# energy.txt: one fprintf of 30 %g (arepo-smuggle:src/logs/global.cc:91)
# Rows are smc_001_edw1_sh03's first and last line: time, Eint/Epot/Ekin totals,
# (int, pot, kin) x 6 types, mass x 6 types, EgyInjection, EnergyMag
ENERGY_T0 = [
    0,
    28.9341,
    0,
    3503.33,
    28.9341,
    0,
    141.356,
    0,
    0,
    3332.14,
    0,
    0,
    28.3882,
    0,
    0,
    1.44061,
    0,
    0,
    0,
    0,
    0,
    0,
    0.0604452,
    1.52038,
    0.0111935,
    0.000796009,
    0,
    0,
    0,
    0,
]
ENERGY_TEND = [
    1.0227,
    32.3744,
    0,
    3445.64,
    32.3744,
    0,
    122.438,
    0,
    0,
    3258.9,
    0,
    0,
    27.0967,
    0,
    0,
    1.3163,
    0,
    0,
    35.8875,
    0,
    0,
    0,
    0.0478371,
    1.52038,
    0.0111935,
    0.000796009,
    0.0126081,
    0,
    0,
    0,
]


def energy_line(row):
    return " ".join(f"{v:g}" for v in row) + "\n"


def test_energy_columns_land_per_type(tmp_path):
    path = tmp_path / "energy.txt"
    path.write_text(energy_line(ENERGY_T0) + energy_line(ENERGY_TEND))
    e = arepo.read_energy(path)
    np.testing.assert_array_equal(e.time, [0, 1.0227])
    # mass block is cols 22-27, indexed by PartType: gas, halo, disk, bulge, new stars, bndry
    np.testing.assert_array_equal(e.mass[0], [0.0604452, 1.52038, 0.0111935, 0.000796009, 0, 0])
    assert e.mass[1, 4] == 0.0126081
    # (int, pot, kin) triplets: gas has Eint, halo has only Ekin, new stars gain Ekin
    assert e.e_int[0, 0] == 28.9341
    assert e.e_kin[0, 1] == 3332.14
    assert e.e_kin[1, 4] == 35.8875
    assert e.e_int[0, 1] == 0
    # run #1 had no EVALPOTENTIAL: every Epot column is 0
    assert not e.has_potential
    assert e.rows_dropped == 0


def test_energy_restart_overlap_dropped(tmp_path):
    mid = list(ENERGY_T0)
    mid[0] = 0.5
    late = list(ENERGY_T0)
    late[0] = 0.7
    path = tmp_path / "energy.txt"
    # first pass reaches 0.7, restart from 0.5 re-logs 0.5 then continues to 1.0227
    path.write_text("".join(energy_line(r) for r in [ENERGY_T0, mid, late, mid, ENERGY_TEND]))
    e = arepo.read_energy(path)
    np.testing.assert_array_equal(e.time, [0, 0.5, 1.0227])
    assert e.rows_dropped == 2


def test_energy_potential_detected_when_logged(tmp_path):
    row = list(ENERGY_T0)
    row[5] = -12.5  # gas Epot
    path = tmp_path / "energy.txt"
    path.write_text(energy_line(row))
    assert arepo.read_energy(path).has_potential


def test_energy_wrong_column_count_raises(tmp_path):
    path = tmp_path / "energy.txt"
    path.write_text(energy_line(ENERGY_T0[:28]))
    with pytest.raises(ValueError, match="expected 30"):
        arepo.read_energy(path)


# memory.txt (arepo-smuggle:src/data/mymalloc.cc:356); SHARED MEMORY variant from
# arepo-smuggle:src/data/memorymanager.cc:151 shares the wording and must not match
MEM_FMT = (
    "\nMEMORY:  Largest Allocation = %g Mbyte  |  Largest Allocation Without Generic = %g Mbyte\n\n"
)
SHARED_FMT = "\nSHARED MEMORY:  Largest Allocation = %g Mbyte  |  Largest Allocation Without Generic = %g Mbyte\n\n"


def test_memory_peak_is_max_not_last_and_ignores_shared(tmp_path):
    path = tmp_path / "memory.txt"
    path.write_text(
        MEM_FMT % (4495.58, 585.595)
        + SHARED_FMT % (9999, 9999)
        # high-water resets on restart, so a later block can be smaller than the true peak
        + MEM_FMT % (1465.62, 175.439)
    )
    m = arepo.read_memory_peak(path)
    assert (m.total_mb, m.without_generic_mb) == (4495.58, 585.595)


def test_memory_without_blocks_raises(tmp_path):
    path = tmp_path / "memory.txt"
    path.write_text(SHARED_FMT % (1.0, 1.0))
    with pytest.raises(ValueError, match="no 'MEMORY:' line"):
        arepo.read_memory_peak(path)


# timebins.txt: block header logs.cc:549, column header logs.cc:631, bin line logs.cc:679.
# Optional columns (smuggle/tracer/dust) are "" or "%10llu  " per Config flag (logs.cc:648-672)
TB_HEAD = "\nSync-Point %d, Time: %.10g, Systemstep: %g\n"
TB_COLS = (
    "Occupied timebins: gravity       hydro     %s     %s     %s  dt            "
    "cumul-grav   cumul-sph A D    avg-time  cpu-frac\n"
)
TB_BIN = (
    " %s  bin=%2d      %10d  %10d  %s  %s %s   %16.12f       %10d  %10d %s %s  %10.2f    %5.1f%%\n"
)
TB_TOTAL = "               ------------------------\nTotal active:   %10d  %10d  %s  %s  %s\n\n"


def tb_block(step, time, systemstep, bins, smuggle=False):
    """bins: (synced, bin, n_grav, n_hydro, dt), highest bin first as AREPO prints them"""
    opt = "smuggle     " if smuggle else ""
    out = TB_HEAD % (step, time, systemstep) + TB_COLS % (opt, "", "")
    for synced, b, ng, nh, dt in bins:
        count = f"{7:10d}  " if smuggle else ""
        out += TB_BIN % (
            "X" if synced else " ",
            b,
            ng,
            nh,
            count,
            "",
            "",
            dt,
            ng,
            nh,
            " ",
            " ",
            0.0,
            0.0,
        )
    return out + TB_TOTAL % (0, 0, "", "", "")


# smc_001_edw1_sh03 Sync-Points 0, 1, 28727 (trimmed to the bins that matter)
TB_RUN1 = [
    (0, 0, 0, [(True, 0, 32594442, 2374442, 0.0)]),
    (
        1,
        3.901290894e-06,
        3.90129e-06,
        [
            (False, 20, 11388642, 108873, 0.001997460937),
            (False, 12, 65, 65, 0.000007802582),
            (True, 11, 5, 5, 0.000003901291),
        ],
    ),
    (
        28727,
        1.0227,
        3.12103e-05,
        [
            (True, 20, 11335477, 74802, 0.001997460937),
            (True, 15, 25765, 25764, 0.000062420654),
            (True, 14, 4, 4, 0.000031210327),
        ],
    ),
]


def test_timebins_smallest_occupied_bin_per_sync_point(tmp_path):
    path = tmp_path / "timebins.txt"
    path.write_text("".join(tb_block(*b) for b in TB_RUN1))
    t = arepo.read_timebins(path)
    np.testing.assert_array_equal(t.time, [0, 3.901290894e-06, 1.0227])
    np.testing.assert_array_equal(t.min_bin, [0, 11, 14])
    np.testing.assert_array_equal(t.min_dt, [0.0, 0.000003901291, 0.000031210327])
    np.testing.assert_array_equal(t.n_grav, [32594442, 5, 4])
    np.testing.assert_array_equal(t.n_hydro, [2374442, 5, 4])
    assert t.rows_dropped == 0


def test_timebins_min_found_regardless_of_print_order(tmp_path):
    # the parser takes the min, it doesn't trust 'last line = lowest bin'
    path = tmp_path / "timebins.txt"
    path.write_text(tb_block(5, 0.1, 1e-5, [(True, 11, 5, 5, 3.9e-6), (False, 20, 9, 9, 2e-3)]))
    assert arepo.read_timebins(path).min_bin.tolist() == [11]


def test_timebins_smuggle_column_shifts_dt(tmp_path):
    # SMUGGLE_STAR_FEEDBACK_LIMIT_GAS_TIMESTEP adds a count column before dt; a fixed index
    # would read that integer count (7) as dt
    path = tmp_path / "timebins.txt"
    path.write_text(tb_block(*TB_RUN1[1], smuggle=True))
    t = arepo.read_timebins(path)
    assert t.min_dt.tolist() == [0.000003901291]
    assert (t.n_grav[0], t.n_hydro[0]) == (5, 5)


def test_timebins_restart_overlap_dropped(tmp_path):
    one = [(True, 14, 4, 4, 3.1e-5)]
    path = tmp_path / "timebins.txt"
    path.write_text(
        "".join(
            tb_block(s, t, 1e-5, one)
            for s, t in [(1, 0.1), (2, 0.2), (3, 0.3), (2, 0.2), (3, 0.35)]
        )
    )
    t = arepo.read_timebins(path)
    np.testing.assert_array_equal(t.time, [0.1, 0.2, 0.35])
    assert t.rows_dropped == 2
