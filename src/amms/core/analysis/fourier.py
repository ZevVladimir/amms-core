""" """

import numpy as np

__all__ = [
    "fourier_phase",
]


def fourier_phase(
    pos: np.ndarray,
    mass: np.ndarray | None = None,
    *,
    m: int = 2,
    r_min: float = 0.0,
    r_max: float = np.inf,
) -> tuple[float, float]:
    """
    Phase (rad) and amplitude A_m of the m-th azimuthal harmonic of face-on positions in r_min <= R < r_max

    Phase is the azimuth of the density maximum
        Defined as: modulo 2*pi/m (m=2: bar axis, 180 deg ambiguous)
            Divide by m not 2 (unlike magclouds disk_utils to allow for use with odd m)
    """
    pos = np.asarray(pos, dtype=float)
    w = np.ones(len(pos)) if mass is None else np.asarray(mass, dtype=float)

    rcyl = np.hypot(pos[:, 0], pos[:, 1])
    sel = (rcyl >= r_min) & (rcyl < r_max)
    if not sel.any():
        raise ValueError(f"no tracers in {r_min} <= R < {r_max}")

    phi = np.arctan2(pos[sel, 1], pos[sel, 0])
    w = w[sel]
    a = np.sum(w * np.cos(m * phi))
    b = np.sum(w * np.sin(m * phi))
    return float(np.arctan2(b, a) / m), float(np.hypot(a, b) / w.sum())
