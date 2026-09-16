"""
Converts from Galactocentric coordinates to equatorial (RA/DEC)

Utilizes astropy which requires extra install `sky`

pos passed should:
    1. Be relative to the MW center by translation not amms.core.analysis.frames.Frame (which performs a rotation)
    2. In kpc, box axes aligned to astropy's Galactocentric convention (x toward Sun's projection onto Galactic plane, z towards north Galactic pole)
    Assumed based on IC build #TODO verify this
"""

from __future__ import annotations

import numpy as np
from astropy import units as u
from astropy.coordinates import ICRS, SkyCoord

__all__ = ["radec_from_galactocentric"]


def radec_from_galactocentric(
    pos_mw_kpc: np.ndarray, **galactocentric_frame_kwargs
) -> tuple[np.ndarray, np.ndarray]:
    """
    Converts the MW centered cartesian positions in kpc to ICRS RA/DEC in deg

    RA gets wrapped to [-180, 180)
    the galactocentric_frame_kwargs are passed on to astropy's galactocentric frame
    """
    pos = np.asarray(pos_mw_kpc, dtype=float)
    galcen = SkyCoord(
        x=pos[:, 0] * u.kpc,
        y=pos[:, 1] * u.kpc,
        z=pos[:, 2] * u.kpc,
        frame="galactocentric",
        **galactocentric_frame_kwargs,
    )
    icrs = galcen.transform_to(ICRS())

    ra = icrs.ra.degree
    # does the wrapping
    ra = np.where(ra > 180.0, ra - 360.0, ra)
    return ra, icrs.dec.degree
