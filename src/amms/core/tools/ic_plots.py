"""
Diagnostic figure for an IC: structure as sampled vs the generator's model
Provide an understanding at a glance that the IC looks reasonable

Usage:
    amms ic-plots IC.hdf5 [--vc GEN.vc] [--r-max KPC] [--bins 40]

Writes <ic_dir>/sanity/<ic_stem>/figures/ic_diagnostics.png
.vc header doubles as .parameters
If --vc is not passed then only particle curves are drawn

Currently:
    MakeGalaxy only:
        units kpc / 1e10 Msun / km/s with its G
        gas 0, halo 1, disk 2, bulge 3
    Frame is constructed from disk stars (PartType2)
    gridded IC is centered wherever the grid put it
    Gas Q uses the IC's u differs in construction from the .vc gas Q which assumes SH03 EOS
    Reads every particle (30M halo for edw1) so requires compute node
"""

from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import numpy as np

from amms.core import ics
from amms.core.analysis import profiles
from amms.core.analysis.frames import Frame
from amms.core.analysis.maps import project_map
from amms.core.codes import makegalaxy
from amms.core.config.paths import ics_root

NAMES = {0: "gas", 1: "halo", 2: "disk", 3: "bulge"}
EXTRA = ("InternalEnergy", "Metallicity", "StellarFormationTime")


def load(path: Path) -> dict[int, dict[str, np.ndarray]]:
    out = {}
    with h5py.File(path, "r") as f:
        mt = f["Header"].attrs["MassTable"]
        for t in NAMES:
            if f"PartType{t}" not in f:
                continue
            g = f[f"PartType{t}"]
            x = {"pos": g["Coordinates"][:].astype(float)}
            x["m"] = (
                g["Masses"][:].astype(float) if "Masses" in g else np.full(len(x["pos"]), mt[t])
            )
            if t in (0, 2):  # halo velocities are unused: 30M x 3 doubles saved
                x["vel"] = g["Velocities"][:].astype(float)
            x.update({k: g[k][:].astype(float) for k in EXTRA if k in g})
            out[t] = x
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="amms ic-plots")
    ap.add_argument("ic", type=Path)
    ap.add_argument("--vc", type=Path, help="generator .vc; MakeGalaxy writes this to its cwd")
    ap.add_argument(
        "--r-max", type=float, help="disk panels [kpc]; default 6 Rd from --vc, else 15"
    )
    ap.add_argument("--bins", type=int, default=40)
    a = ap.parse_args(argv)

    import matplotlib.pyplot as plt  # allows module to remain importable without matplotlib

    from amms.core.plotting.maps import show_map
    from amms.core.plotting.provenance import savefig

    ic = a.ic.resolve()
    vc = makegalaxy.read_vc(a.vc) if a.vc else None
    par = vc.params if vc else None
    budget = {c.ptype: c.mass for c in makegalaxy.component_budget(par)} if par else {}
    p = load(ic)

    if 2 not in p:
        ap.error("no PartType2 (disk stars) to define the frame from")
    fr = Frame.from_tracers(p[2]["pos"], p[2]["vel"], p[2]["m"], tracers="disk (PartType2)")
    for x in p.values():
        x["pos"] = fr.positions(x["pos"])
        if "vel" in x:
            x["vel"] = fr.velocities(x["vel"])

    G = makegalaxy.G_CODE
    rd = par["Rd"] if par else None
    r_max = a.r_max or (6 * rd if rd else 15.0)
    e_cyl = np.linspace(0, r_max, a.bins + 1)
    rc = 0.5 * (e_cyl[1:] + e_cyl[:-1])
    msun = 1e10  # code mass to Msun conversion for plotting

    fig, ax = plt.subplots(3, 3, figsize=(13, 12), constrained_layout=True)
    a_rho, a_sig, a_vc, a_q, a_z, a_face, a_edge, a_met, a_age = ax.ravel()

    # (a) spherical components vs Hernquist
    e_sph = np.geomspace(0.05, par["R200"] if par else 100.0, a.bins + 1)
    rs = np.sqrt(e_sph[1:] * e_sph[:-1])
    for t in (1, 3):
        if t in p:
            r = np.linalg.norm(p[t]["pos"], axis=1)
            a_rho.loglog(
                rs,
                profiles.shell_density(r, p[t]["m"], e_sph) * msun,
                color=f"C{t}",
                label=NAMES[t],
            )
    if par:
        a_rho.loglog(
            rs,
            profiles.hernquist_density(rs, budget[1], par["RH"]) * msun,
            color="C1",
            ls="--",
            label="halo model",
        )
        if 3 in budget:
            a_rho.loglog(
                rs,
                profiles.hernquist_density(rs, budget[3], par["a"]) * msun,
                color="C3",
                ls="--",
                label="bulge model",
            )
    a_rho.set(xlabel="r [kpc]", ylabel=r"$\rho$ [M$_\odot$ kpc$^{-3}$]", title="spherical density")
    a_rho.legend(fontsize=7)

    # (b) disk components vs exponential
    cyl = {}
    for t in (0, 2):
        if t in p:
            cyl[t] = profiles.cylindrical(p[t]["pos"], p[t]["vel"])
            a_sig.semilogy(
                rc,
                profiles.annulus_density(cyl[t][0], p[t]["m"], e_cyl) * msun,
                color=f"C{t}",
                label=NAMES[t],
            )
    if par:
        a_sig.semilogy(
            rc,
            profiles.exponential_surface_density(rc, budget[2], rd) * msun,
            color="C2",
            ls="--",
            label="disk model",
        )
        h_gas = {0: rd, 1: par["GasAl"] * rd}.get(
            int(par["GasD"])
        )  # GasD=2 needs PowerLawGamma, which is not in the header
        if h_gas and 0 in budget:
            a_sig.semilogy(
                rc,
                profiles.exponential_surface_density(rc, budget[0], h_gas) * msun,
                color="C0",
                ls="--",
                label="gas model",
            )
    a_sig.set(xlabel="R [kpc]", ylabel=r"$\Sigma$ [M$_\odot$ kpc$^{-2}$]", title="surface density")
    a_sig.legend(fontsize=7)

    # (c) rotation: model v_c vs spherical M(<r) vs what the particles actually do
    r_all = np.concatenate([np.linalg.norm(x["pos"], axis=1) for x in p.values()])
    m_all = np.concatenate([x["m"] for x in p.values()])
    vc_part = profiles.vc_enclosed(r_all, m_all, rc, G)
    if vc:
        k = vc.r <= r_max
        a_vc.plot(
            vc.r[k], np.sqrt(np.clip(vc.vc2_total[k], 0, None)), color="k", label="model total"
        )
        for name, t, v2 in (
            ("disk (tree)", 2, vc.vc2_disk),
            ("halo", 1, vc.vc2_halo),
            ("bulge", 3, vc.vc2_bulge),
        ):
            if v2[k].any():
                a_vc.plot(
                    vc.r[k],
                    np.sqrt(np.clip(v2[k], 0, None)),
                    color=f"C{t}",
                    ls=":",
                    label=f"model {name}",
                )
    a_vc.plot(rc, vc_part, color="0.5", label="particles, spherical M(<r)")
    for t, (R, _, v_phi) in cyl.items():
        a_vc.plot(
            rc,
            profiles.binned(R, v_phi, e_cyl, stat="mean", weights=p[t]["m"]),
            color=f"C{t}",
            label=rf"{NAMES[t]} $\langle v_\phi \rangle$",
        )
    a_vc.set(xlabel="R [kpc]", ylabel="v [km/s]", title="rotation")
    a_vc.legend(fontsize=7)

    # (d) Toomre Q; use kappa from the model curve when available
    kap = (
        np.interp(rc, vc.r, profiles.kappa(vc.r, vc.vc2_total))
        if vc
        else profiles.kappa(rc, vc_part**2)
    )
    if 2 in cyl:
        R, v_R, _ = cyl[2]
        sig_R = profiles.binned(R, v_R, e_cyl, stat="std")
        sigma = profiles.annulus_density(R, p[2]["m"], e_cyl)
        a_q.plot(rc, profiles.toomre_q_stars(sig_R, kap, sigma, G), color="C2", label="stars")
    if 0 in cyl and "InternalEnergy" in p[0]:
        R = cyl[0][0]
        c_s = np.sqrt(makegalaxy.GAMMA * (makegalaxy.GAMMA - 1) * p[0]["InternalEnergy"])
        cs = profiles.binned(R, c_s, e_cyl, stat="mean", weights=p[0]["m"])
        sigma = profiles.annulus_density(R, p[0]["m"], e_cyl)
        a_q.plot(rc, profiles.toomre_q_gas(cs, kap, sigma, G), color="C0", label="gas (IC u)")
    if vc:
        k = vc.q_r <= r_max
        a_q.plot(vc.q_r[k], vc.q_stars[k], color="C2", ls="--", label="stars model")
        a_q.plot(vc.q_r[k], vc.q_gas[k], color="C0", ls=":", label="gas model (SH03 EOS)")
    a_q.axhline(1, color="0.6", lw=0.8)
    a_q.set(xlabel="R [kpc]", ylabel="Q", yscale="log", title="Toomre Q")
    a_q.legend(fontsize=7)

    # (e) thickness: mass weighted median |z| (background cells carry ~no mass so we want to ignore)
    for t in cyl:
        z = np.abs(p[t]["pos"][:, 2])
        a_z.plot(
            rc,
            profiles.binned(cyl[t][0], z, e_cyl, stat="median", weights=p[t]["m"]),
            color=f"C{t}",
            label=NAMES[t],
        )
    if par:
        a_z.axhline(
            profiles.SECH2_MEDIAN * par["z0"] * rd,
            color="C2",
            ls="--",
            label=r"disk model, sech$^2$",
        )
    a_z.set(xlabel="R [kpc]", ylabel="median |z| kpc", title="thickness")
    a_z.legend(fontsize=7)

    # (f, g) gas maps
    if 0 in p:
        for axx, axes, name in ((a_face, "xy", "face-on"), (a_edge, "xz", "edge-on")):
            mp = project_map(
                p[0]["pos"],
                p[0]["m"] * msun,
                axes=axes,
                extent=r_max,
                bins=128,
                per_area=True,
                quantity=r"$\Sigma_{\rm gas}$",
                unit=r"M$_\odot$ kpc$^{-2}$",
            )
            show_map(mp, axx, title=f"gas {name}")

    # (h, i) one quantity per panel: Z and formation time have different units
    for axx, key, xlabel in (
        (a_met, "Metallicity", "Z"),
        (a_age, "StellarFormationTime", "formation time [code]"),
    ):
        have = [t for t in (0, 2) if key in p.get(t, {})]
        for t in have:
            axx.hist(p[t][key], bins=50, histtype="step", color=f"C{t}", label=NAMES[t])
        if have:
            axx.set(xlabel=xlabel, yscale="log", title=key)
            axx.legend(fontsize=7)
        else:
            axx.text(
                0.5, 0.5, f"no {key} in this IC", ha="center", va="center", transform=axx.transAxes
            )
            axx.set_axis_off()

    fp = ics.fingerprint(
        ic
    )  # ICs get revised in place so figures carry the specific hash of the IC checked
    tags = ics.read_tags(ics_root() / "ic_tags.yaml")
    tag = next((t.tag for t in tags.values() if t.sha256 == fp.sha256), None)
    out = ic.parent / "sanity" / ic.stem / "figures"
    out.mkdir(parents=True, exist_ok=True)
    path = savefig(
        fig,
        out / "ic_diagnostics.png",
        source=tag or ic.name,
        repo=Path(__file__).parent,
        extra={
            "ic_sha256": fp.sha256,
            "vc": str(a.vc.resolve()) if a.vc else None,
            "frame": fr.to_dict(),
        },
        dpi=200,
        bbox_inches="tight",
    )
    print(f"{tag or 'unregistered'}: {path}")


if __name__ == "__main__":
    main()
