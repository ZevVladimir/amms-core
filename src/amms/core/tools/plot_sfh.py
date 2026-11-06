"""
Star formation history of an AREPO run from sfr.txt: SFR(t) and cumulative stellar mass formed

Usage:
    amss plot-sfh SIM_ID [--param param.txt] [--bin-myr 10]

Two SFR curves defined below:
    sfr     per-step instantaneous rate carried by the gas (taken from sfr.txt column 3)
    binned  mean rate of what actually spawned, from the per-step mass
The per-step realised column is too stochastic to read unbinned and thus is not plotted directly
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from amms.core.analysis.sfr import sfh
from amms.core.codes import arepo
from amms.core.config.paths import products_root, sims_root
from amms.core.ids import SimID
from amms.core.plotting.provenance import savefig


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="amms plot-sfh")
    ap.add_argument("sim_id", type=SimID.parse)
    ap.add_argument("--param", default="param.txt", help="param file the run used")
    ap.add_argument("--bin-myr", type=float, default=10.0)
    a = ap.parse_args(argv)

    run_dir = sims_root() / a.sim_id.project / str(a.sim_id)
    p = arepo.read_usedvalues(run_dir / f"{a.param}-usedvalues")
    units = arepo.Units.from_usedvalues(p)
    sfr_path = run_dir / p["OutputDir"] / "sfr.txt"
    s = arepo.read_sfr(sfr_path)

    t = s.time * units.time_gyr
    m_step = s.mass_formed_step * units.mass_msun
    m_cum = s.mass_formed_cum * units.mass_msun
    dt = a.bin_myr / 1e3
    # Only use full bins since partial bins look like SFR drops
    edges = t[0] + dt * np.arange(int((t[-1] - t[0]) // dt) + 1)
    edges, rate = sfh(t, m_step, bins=edges)

    fig, (ax0, ax1) = plt.subplots(2, 1, sharex=True, figsize=(6, 5))
    ax0.plot(t, s.sfr, lw=0.5, alpha=0.4, label="instantaneous (gas)")
    ax0.stairs(rate, edges, lw=1.5, label=f"formed, {a.bin_myr:g} Myr bins")
    ax0.set_ylabel(r"SFR [$M_\odot\,\mathrm{yr}^{-1}$]")
    ax0.legend(fontsize=8)
    ax1.plot(t, m_cum)
    ax1.set_ylabel(r"$M_\star$ formed [$M_\odot$]")
    ax1.set_xlabel("t [Gyr]")

    out = products_root() / str(a.sim_id) / "figures"
    out.mkdir(parents=True, exist_ok=True)
    savefig(
        fig,
        out / "sfh_sfrtxt.png",
        source=a.sim_id,
        repo=Path(__file__).parent,
        extra={"sfr_txt": str(sfr_path), "bin_myr": a.bin_myr, "rows_dropped": s.rows_dropped},
        dpi=200,
        bbox_inches="tight",
    )
    print(f"Final M* formed {m_cum[-1]:.3g} Msun, last-bin SFR {rate[-1]:.3g} Msun/yr")


if __name__ == "__main__":
    main()
