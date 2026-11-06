"""
Pins the AREPO output-file parsers in amms.core.codes.arepo against the formats this build writes.

Fixtures are generated with the upstream printf formats rather than typed by hand, so a test
checks the parser against what AREPO emits, not against my reading of it:
    sfr.txt          arepo-smuggle:src/cooling_sfr/starformation.cc:646
    cpu.txt          arepo-smuggle:src/logs/logs.cc:919-926
    -usedvalues      arepo-smuggle:src/io/parameters.cc:124-145 (MAXLEN_PARAM_TAG 50, reals as %g)
    arepoconfig.h    arepo-smuggle:buildsystem/prepare-config.py:55-62,95
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
