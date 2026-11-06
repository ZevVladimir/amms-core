"""
Sanity check the AREPO snapshots
    finite positions
    gas inside the box
    no duplicate positions
    per-type extent

Usage:
    amms check-snap SNAP.hdf5 [SNAP.hdf5 ...] [--margin 10]

Prints a markdown table per snapshot for use in Obsidian. Doesn't write anything

Currently
    Positions are in code units, same as BoxSize
    Extent is measured from BoxSize / 2 (as in the isolated runs at the box center)
        This needs to be adjusted for when the center changes such as with interacting galaxies
    Extent is report without a runaway threshold set
"""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np

from amms.core.analysis import sanity
from amms.core.checks import CheckResult, Status, worst

TYPE_NAMES = ["gas", "halo", "disk", "bulge", "stars", "bndry"]


def check(path: Path, margin: float) -> list[CheckResult]:
    with h5py.File(path, "r") as f:
        box = float(f["Header"].attrs["BoxSize"])
        pos = {t: f[f"PartType{t}/Coordinates"][:] for t in range(6) if f"PartType{t}" in f}
    center = np.full(3, box / 2)

    results = []
    for t, p in pos.items():
        results.append(sanity.check_finite(f"finite_{TYPE_NAMES[t]}", p))
        results.append(
            CheckResult(
                f"r_max_{TYPE_NAMES[t]}",
                Status.PASS,
                sanity.max_radius(p, center),
                None,
                "from BoxSize/2, not judged",
            )
        )
    if 0 in pos:
        results.append(sanity.check_in_box("gas_in_box", pos[0], box, margin=margin))
        results.append(sanity.check_unique_positions("unique_gas", pos[0]))
    # A newly spawned star sits on its parent cell's position. So we would expect to see cross-type duplicates
    results.append(
        sanity.check_unique_positions("unique_all", np.concatenate(list(pos.values()))),
        on_duplicate=Status.WARN,
    )

    return results


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="amms check-snap")
    ap.add_argument("snaps", nargs="+", type=Path)
    ap.add_argument(
        "--margin", type=float, default=10.0, help="WARN if gas is closer than this to a box face"
    )
    a = ap.parse_args(argv)

    for snap in a.snaps:
        results = check(snap, a.margin)
        print(f"\n**{snap.name}**: {worst(results).value}\n")
        print("| Check | Status | Value | Expected | Detail |\n|---|---|---|---|---|")
        for r in results:
            value = f"{r.value:.6g}" if isinstance(r.value, float) else r.value
            print(
                f"| {r.name} | {r.status.value} | {value} | {'' if r.expected is None else r.expected} | {r.detail} |"
            )


if __name__ == "__main__":
    main()
