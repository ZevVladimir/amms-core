"""
Summarize an AREPO run as Markdown tables to be used in Obsidian

Usage:
    amms run-summary RUN_DIR [--param param.txt] [--log JOB.out ...] [--depth N]

Reads from
    <RUN_DIR>/<param>-usedvalues for (units, TimeMax, OutputDir)
    OutputDir for cpu.txt, sfr.txt, newest snap_*.hdf5 header

Parsing is done by amms.core.codes.arepo
"""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py

from amms.core.codes import arepo

TYPE_NAMES = ["gas", "halo", "disk", "bulge", "stars", "bndry"]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="amms run_summary")
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--param", default="param.txt", help="param file the run used")
    ap.add_argument("--log", nargs="+", type=Path, default=[], help="job .out file(s) all restarts")
    ap.add_argument("--depth", type=int, default=1, help="deepest timer level shown")
    a = ap.parse_args(argv)

    p = arepo.read_usedvalues(a.run_dir / f"{a.param}-usedvalues")
    units = arepo.Units.from_usedvalues(p)
    out = a.run_dir / p["OutputDir"]
    cpu = arepo.read_cpu(out / "cpu.txt")
    tmax = float(p["TimeMax"])
    wall_h = cpu.total_s / 3600

    rows = [
        ("Sim time reached", f"{cpu.time * units.time_myr:.1f} of {tmax * units.time_myr:.0f} Myr"),
        ("Steps / MPI tasks", f"{cpu.step} / {cpu.ntask}"),
        ("Wall time", f"{wall_h:.2f} h"),
        ("Speed", f"{cpu.time * units.time_myr / wall_h:.1f} Myr per wall-hour"),
    ]
    if a.log:
        n = sum(f.read_text().count("Peano grid is not fine enough") for f in a.log)
        rows.append(("Peano overrides", str(n)))
    if (out / "sfr.txt").exists():
        s = arepo.read_sfr(out / "sfr.txt")
        rows += [
            ("SFR (final, instantaneous)", f"{s.sfr[-1]:.3g} Msun/yr"),
            ("Stellar mass formed", f"{s.mass_formed_cum[-1] * units.mass_msun:.3g} Msun"),
        ]
        if s.rows_dropped:
            rows.append(("sfr.txt rows superseded by restarts", str(s.rows_dropped)))
    snaps = sorted(out.glob("snap_*.hdf5"))
    if snaps:
        with h5py.File(snaps[-1], "r") as f:
            n = f["Header"].attrs["NumPart_Total"]
        counts = " · ".join(f"{TYPE_NAMES[i]} {c:,}" for i, c in enumerate(n) if c)
        rows.append((f"Particles ({snaps[-1].name})", counts))

    print("| Quantity | Value |\n|---|---|")
    for k, v in rows:
        print(f"| {k} | {v} |")
    print("\n| Timer | Wall [s] | Share |\n|---|---|---|")
    for t in cpu.timers:
        if t.depth <= a.depth:
            print(f"| {'↳ ' * t.depth}{t.name} | {t.cumulative_s:.1f} | {t.cumulative_pct:.1f}% |")


if __name__ == "__main__":
    main()
