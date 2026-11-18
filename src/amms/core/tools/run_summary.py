"""
Summarize an AREPO run as Markdown tables that are easily put into Obsidian

Usage:
    amms run-summary RUN_DIR [--param param.txt] [--log JOB.out ...] [--depth N] [--ic IC.hdf5 | --no-ic]

Reads from:
    <RUN_DIR>/<param>-usedvalues for units, TimeMake, OutputDir, MaxMemSize
    OutputDir: for cpu.txt, sfr.txt, energy.txt, timebins.txt, memory.txt, end, newest snap header
    The IC (first: --ic if not then SIM_ID tag in ic_tags.yaml if not then InitCondFile), sha256-checked against its own tag

    Parsing done by amms.core.codes.arepo
Currently
    Masses from energy.txt. Don't read particle data
    stars_vs_sfrtxt assumes no stellar mass return (due to initial run config might change). With mass return it FAILs and needs GFM_InitialMass instead
    Gas+stars conservation is reported but not judged
"""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import h5py
import numpy as np

from amms.core import ics
from amms.core.analysis import sanity
from amms.core.checks import CheckResult, Status, worst
from amms.core.codes import arepo
from amms.core.config.paths import ics_root, products_root
from amms.core.ids import InvalidSimID, SimID

TYPE_NAMES = ["gas", "halo", "disk", "bulge", "stars", "bndry"]
GIB = 1024**3
MEM_WARN = 0.8  # fraction of MaxMemSize, AREPO aborts at 1.0
FORMED_RTOL = 1e-4  # energy.txt has 6 digits and can be one step's formation apart from sfr.txt


def _sim_id(run_dir: Path) -> SimID | None:
    try:
        return SimID.parse(run_dir.resolve().name)
    except InvalidSimID:
        return None


def resolve_ic(run_dir: Path, ic_arg: Path | None, params: dict[str, str]):
    """
    Order of precedence: --ic then the SIM_ID's tag (registry path) then InitCondFile
    if the run has a tag the chosen file's sha256 is checked against it
    ICs are revised in place so can't just trust a path
    """
    sid = _sim_id(run_dir)
    tag = sid.ic if sid else None
    registry = ics_root() / "ic_tags.yaml"
    tags = ics.read_tags(registry) if tag else {}
    if ic_arg:
        path = ic_arg
    elif tag in tags:
        path = Path(tags[tag].path)
    else:
        f = Path(params["InitCondFile"])
        f = f if f.is_absolute() else run_dir / f
        path = f if f.exists() else f.with_name(f.name + ".hdf5")  # AREPO appends it for HDF5 ics
    if not path.exists():
        return None, [
            CheckResult("ic_found"),
            Status.WARN,
            str(path),
            None,
            "no IC; t=0 not compared",
        ]
    if tag:
        return path, [ics.check_ic_tag(tag, path, registry)]
    return path, [
        CheckResult("ic_tag", Status.WARN, None, None, "run dir is not a SIM_ID; IC unverified")
    ]


def plot_health(
    e: arepo.EnergyLog, tb: arepo.TimebinLog, units: arepo.Units, sim_id: SimID, out: Path
) -> Path:
    import matplotlib.pyplot as plt  # tables should work in venv without matplotlib

    from amms.core.plotting.provenance import savefig

    t = e.time * units.time_gyr
    m = e.mass * units.mass_msun
    erg = units.mass_g / units.hubble * units.velocity_cm_s**2  # code energy conversion to ergs

    fig, (ax0, ax1, ax2) = plt.subplots(3, 1, sharex=True, figsize=(6, 7.5))
    # color = ParType in every panel
    ax0.plot(t, m[:, 0], color="C0", label="gas")
    ax0.plot(t, m[:, 4], color="C4", label="new stars")
    ax0.plot(t, m[:, 0] + m[:, 4], color="0.4", ls=":", label="gas + new stars")
    ax0.set_ylabel(r"$M$ [$M_\odot$]")
    ax0.legend(fontsize=8)

    live = tb.min_dt > 0  # step 0 sits in bin 0 with dt 0
    t_tb = tb.time[live] * units.time_gyr
    dt_kyr = tb.min_dt[live] * units.time_myr * 1e3
    # min within 1 Myr windows: the smallest bin flickers between neighbors each sync point
    # Floor is what matters for detecting if the time scale got too small
    edges = np.arange(t_tb[0], t_tb[-1] + 1e-3, 1e-3)
    starts = np.searchsorted(t_tb, edges[:-1])
    keep = np.unique(starts[starts < len(t_tb)])
    ax1.stairs(np.minimum.reduceat(dt_kyr, keep), np.append(t_tb[keep], t_tb[-1]), color="0.2")
    ax1.set_yscale("log")
    ax1.set_ylabel("smallest dt [kyr]")

    for k in range(6):
        if e.e_kin[:, k].any():
            name = "new stars" if k == 4 else TYPE_NAMES[k]
            ax2.plot(t, e.e_kin[:, k] * erg, color=f"C{k}", label=f"{name} kinetic")
    ax2.plot(t, e.e_int[:, 0] * erg, color="C0", ls="--", label="gas thermal")
    ax2.set_yscale("log")  # halo Ekin is ~100x gas; new star zeros at t=0 are masked
    ax2.set_ylabel("E [erg]")
    ax2.set_xlabel("t [Gyr]")
    ax2.legend(fontsize=7, loc="center left", bbox_to_anchor=(1.01, 0.5))

    out.mkdir(parents=True, exist_ok=True)
    path = savefig(
        fig,
        out / "run_health.png",
        source=sim_id,
        repo=Path(__file__).parent,
        extra={"energy_rows_dropped": e.rows_dropped, "timebins_rows_dropped": tb.rows_dropped},
        dpi=200,
        bbox_inches="tight",
    )
    plt.close(fig)
    return path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="amms run-summary")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--param", default="param.txt", help="param file the run used")
    ap.add_argument(
        "--log",
        nargs="+",
        type=Path,
        default=[],
        help="this run's job .out file(s), including restarts; not smoke tests",
    )
    ap.add_argument("--depth", type=int, default=1, help="deepest timer level shown")
    ap.add_argument("--no-fig", action="store_true", help="tables only")
    g = ap.add_mutually_exclusive_group()
    g.add_argument(
        "--ic", type=Path, help="IC to compare t=0 masses with; default: from SIM_ID tag"
    )
    g.add_argument("--no-ic", action="store_true", help="skip the IC check (hashes + reads the IC)")
    a = ap.parse_args(argv)

    p = arepo.read_usedvalues(a.run_dir / f"{a.param}-usedvalues")
    units = arepo.Units.from_usedvalues(p)
    out = a.run_dir / p["OutputDir"]
    cpu = arepo.read_cpu(out / "cpu.txt")
    tmax = float(p["TimeMax"])
    wall_h = cpu.total_s / 3600
    checks: list[CheckResult] = []
    dropped: dict[str, int] = {}

    rows = [
        ("Finished cleanly", "yes" if (out / "end").exists() else "**NO** (no output/end)"),
        ("Sim time reached", f"{cpu.time * units.time_myr:.1f} of {tmax * units.time_myr:.0f} Myr"),
        ("Steps / MPI tasks", f"{cpu.step} / {cpu.ntask}"),
        ("Wall time", f"{wall_h:.2f} h"),
        ("Speed", f"{cpu.time * units.time_myr / wall_h:.1f} Myr per wall-hour"),
    ]

    if a.log:
        n = sum(f.read_text().count("Peano grid is not fine enough") for f in a.log)
        rows.append(("Peano overrides", str(n)))

    s = arepo.read_sfr(out / "sfr.txt") if (out / "sfr.txt").exists() else None
    if s:
        dropped["sfr"] = s.rows_dropped
        rows += [
            ("SFR (final, instantaneous)", f"{s.sfr[-1]:.3g} Msun/yr"),
            ("Stellar mass formed", f"{s.mass_formed_cum[-1] * units.mass_msun:.3g} Msun"),
        ]

    e = tb = None
    if (out / "energy.txt").exists():
        e = arepo.read_energy(out / "energy.txt")
        dropped["energy"] = e.rows_dropped
        baryons = e.mass[:, 0] + e.mass[:, 4]
        rows.append(("Gas + new stars, end / t=0", f"{baryons[-1] / baryons[0]:.6f} (not judged)"))
        if not e.has_potential:
            rows.append(("Energy conservation", "not checkable (no EVALPOTENTIAL config param)"))
        if s:
            i = int(np.searchsorted(s.time, e.time[-1], side="right")) - 1
            checks.append(
                sanity.check_relative(
                    "stars_vs_sfrtxt",
                    float(e.mass[-1, 4]),
                    float(s.mass_formed_cum[i]),
                    rtol=FORMED_RTOL,
                    detail="PartType4 mass (energy.txt) vs formed (sfr.txt)",
                )
            )
        if not a.no_ic:
            ic, res = resolve_ic(a.run_dir, a.ic, p)
            checks += res
            if ic:
                icm = ics.component_masses(ic, ics.read_header(ic))
                floor = float(p.get("MinimumDensityOnStartUp", 0))
                for t in range(6):
                    if icm.get(t, 0.0) or e.mass[0, t]:
                        r = sanity.check_relative(
                            f"t0_mass_{TYPE_NAMES[t]}",
                            float(e.mass[0, t]),
                            icm.get(t, 0.0),
                            rtol=ics.MASS_RTOL,
                            detail=f"energy.txt t=0 vs {ic.name}",
                        )
                        # init.cc:1419-1424 raises cells below MinimumDensityOnStartUp to it and rescales their mass
                        # So AREPO starts with MORE gas than the IC holds
                        excess = float(e.mass[0, 0]) - icm.get(0, 0.0)
                        # most the floor can add: every cell in the box raised to it
                        # (mesh tiles the box exactly, sum m/rho = BoxSize^3 from run 1)
                        cap = floor * float(p["BoxSize"]) ** 3
                        if t == 0 and r.status is Status.FAIL and floor > 0 and 0 < excess <= cap:
                            r = dataclasses.replace(
                                r,
                                status=Status.WARN,
                                detail=f"{r.detail}; excess = {excess / cap:.1%} of "
                                f"MinimumDensityOnStartUp x BoxSize^3 (init.cc:1419)",
                            )
                        checks.append(r)

    if (out / "timebins.txt").exists():
        tb = arepo.read_timebins(out / "timebins.txt")
        dropped["timebins"] = tb.rows_dropped
        live = tb.min_dt > 0  # step 0 sits in bin 0 with dt 0
        j = np.flatnonzero(live)[np.argmin(tb.min_dt[live])]
        rows.append(
            (
                "Smallest timestep",
                f"{tb.min_dt[j] * units.time_myr * 1e3:.3g} kyr (bin {tb.min_bin[j]}, "
                f"t = {tb.time[j] * units.time_myr:.3g} Myr, {tb.n_hydro[j]} cells)",
            )
        )

    if (out / "memory.txt").exists():
        mem = arepo.read_memory_peak(out / "memory.txt")
        maxmem = float(p["MaxMemSize"])
        frac = mem.without_generic_mb / maxmem
        checks.append(
            CheckResult(
                "memory_peak",
                Status.WARN if frac > MEM_WARN else Status.PASS,
                round(frac, 3),
                MEM_WARN,
                f"{mem.without_generic_mb:.0f} of {maxmem:.0f} MB/task without generic buffers, +-5%",
            )
        )

    if dropped:
        rows.append(
            ("Log rows superseded by restarts", ", ".join(f"{k} {v}" for k, v in dropped.items()))
        )

    du = arepo.disk_usage(out)
    per_snap = du.snap_bytes / du.n_snap if du.n_snap else 0.0
    rows += [
        ("Snapshots", f"{du.n_snap} x {per_snap / GIB:.2f} GiB = {du.snap_bytes / GIB:.1f} GiB"),
        ("Restart files (fixed)", f"{du.restart_bytes / GIB:.1f} GiB"),
        ("Logs / other", f"{du.log_bytes / GIB:.2f} / {du.other_bytes / GIB:.2f} GiB"),
    ]
    n_exp = arepo.expected_snapshots(p)
    if n_exp:
        # logs scale with sim time reached, restart set doesn't grow
        logs_end = du.log_bytes * tmax / cpu.time if cpu.time else du.log_bytes
        total = n_exp * per_snap + du.restart_bytes + logs_end + du.other_bytes
        rows.append(("Projected at TimeMax", f"{n_exp} snapshots, {total / GIB:.1f} GiB"))

    snaps = sorted(out.glob("snap_*.hdf5"))
    if snaps:
        with h5py.File(snaps[-1], "r") as f:
            n = f["Header"].attrs["NumPart_Total"]
        counts = " · ".join(f"{TYPE_NAMES[i]} {c:,}" for i, c in enumerate(n) if c)
        rows.append((f"Particles ({snaps[-1].name})", counts))

    print("| Quantity | Value |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")
    if checks:
        print(f"\n**Checks: {worst(checks).value}**\n")
        print("| Check | Status | Value | Expected | Detail |\n|---|---|---|---|---|")
        for r in checks:
            value = f"{r.value:.3g}" if isinstance(r.value, float) else r.value
            if isinstance(value, str) and len(value) == 64:
                value = value[:12] + "..."  # sha256
            print(
                f"| {r.name} | {r.status.value} | {value} | {'' if r.expected is None else r.expected} | {r.detail} |"
            )
    print("\n| Timer | Wall [s] | Share |\n|---|---|---|")
    for t in cpu.timers:
        if t.depth <= a.depth:
            print(f"| {'↳ ' * t.depth}{t.name} | {t.cumulative_s:.1f} | {t.cumulative_pct:.1f}% |")

    sid = _sim_id(a.run_dir)
    if a.no_fig or e is None or tb is None:
        pass
    elif sid is None:
        print("\nNo figure: run dir is not a SIM_ID, so it has not products dataset")
    else:
        print(f"\nFigure: {plot_health(e, tb, units, sid, products_root() / str(sid) / 'figures')}")


if __name__ == "__main__":
    main()
