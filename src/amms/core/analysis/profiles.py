"""
Construct radial, vertical profiles, and Toomre Q from particle arrays

Takes in arrays that are in a galaxy frame (centered, disk in x-y) returns numbers
Numpy only
Units are the caller's; G must be in the same units
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "SECH2_MEDIAN",
    "annulus_density",
    "binned",
    "cylindrical",
    "exponential_surface_density",
    "hernquist_density",
    "kappa",
    "shell_density",
    "toomre_q_gas",
    "toomre_q_stars",
    "vc_enclosed",
]

SECH2_MEDIAN = float(np.arctanh(0.5))  # median |z| / z0 for rho ~ sech^2(z/z0): CDF of |z| is tanh


def shell_density(r, m, edges):
    """
    Calculates the spherical density: mass per shell / volume of shell
    """
    mass, _ = np.histogram(r, bins=edges, weights=m)
    return mass / (4 / 3 * np.pi * np.diff(edges**3))


def annulus_density(R, m, edges):
    """
    Surface density: mass per annulus (all z) / annulus area
    """
    mass, _ = np.histogram(R, bins=edges, weights=m)
    return mass / (np.pi * np.diff(edges**2))


def cylindrical(pos, vel):
    """
    Returns (R, v_R, v_phi) for a frame with the disk in x-y plane
    R=0 returns NaN velocities
    v_R = v · hat{R} = (x v_x + y v_y) / R
    v_phi = v · hat{phi} = (x v_y - y v_x) / R
    """
    x, y = pos[:, 0], pos[:, 1]
    R = np.hypot(x, y)
    return R, (x * vel[:, 0] + y * vel[:, 1]) / R, (x * vel[:, 1] - y * vel[:, 0]) / R


def binned(x, values, edges, *, stat: str, weights=None):
    """
    Per-bin weighted 'mean' | 'std' | 'median'
        NaN where a bin has < 2 particles
        Weight gas by mass. Avoids having the numerous gridded IC's background cells that have ~no mass
             overwhelm count-based statistics
    """
    if stat not in ("mean", "std", "median"):
        raise ValueError(f"unknown stat {stat!r}")

    w = np.ones(len(x)) if weights is None else np.asarray(weights, dtype=float)
    idx = np.digitize(x, edges) - 1
    out = np.full(len(edges) - 1, np.nan)

    for i in range(len(out)):
        sel = idx == i
        if sel.sum() < 2:
            continue
        v, wi = values[sel], w[sel]
        if stat == "median":
            o = np.argsort(v)
            c = np.cumsum(wi[o])
            out[i] = v[o][np.searchsorted(c, 0.5 * c[-1])]
        else:
            mu = np.average(v, weights=wi)
            out[i] = mu if stat == "mean" else np.sqrt(np.average((v - mu) ** 2, weights=wi))
    return out


def vc_enclosed(r, m, r_eval, G):
    """
    sqrt(G M(<r) / r): exact in spherical components; off by ~10% where a disk dominates
    """
    o = np.argsort(r)
    cum = np.cumsum(m[o])
    k = np.searchsorted(r[o], r_eval, side="right")
    return np.sqrt(G * np.where(k > 0, cum[np.maximum(k - 1, 0)], 0.0) / r_eval)


def kappa(R, vc2):
    """
    Epicyclic frequency calculated from v_c^2(R):
        kappa^2 = (1/R) d(v_c^2)/dR + 2 v_c^2 / R^2
    """
    k2 = np.gradient(vc2, R) / R + 2 * vc2 / R**2
    return np.sqrt(np.clip(k2, 0, None))


def toomre_q_stars(sigma_R, kappa, sigma, G):
    return sigma_R * kappa / (3.36 * G * sigma)  # Toomre 1964, as makegalaxy:toomre.c:65


def toomre_q_gas(c_s, kappa, sigma, G):
    return c_s * kappa / (np.pi * G * sigma)


def hernquist_density(r, mass, a):
    """
    makegalaxy:halo.c:204, makegalaxy:bulge.c:167
    rho(r) from eqtn 6 Hernquist 1989
    """
    return mass / (2 * np.pi) * a / (r * (r + a) ** 3)


def exponential_surface_density(R, mass, h):
    """
    makegalaxy:disk.c:288
    Rd from Mo, Mao, & White 1998
    IC construction Springel, Di Matteo, & Hernquist (2005)
    """
    return mass / (2 * np.pi * h**2) * np.exp(-R / h)
