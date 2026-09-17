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

__all__ = ["radec_from_galactocentric", "sky_aspect", "sky_bins"]


def sky_aspect(lat_center: float) -> float:
    """
    Calculates the display/box aspect (y-scale / x_scale) that corrects RA-like circles that shrink by cos(lat) away from the equator

    This allows for the bins to remain square

    This can be passed to show_map(..., aspect=sky_aspect(dec_center)) and to sky_bins() to make a box/pixel represent angular size not the raw lon/lat degrees
    """
    return 1.0 / np.cos(np.radians(lat_center))


def sky_bins(
    lon_range: tuple[float, float],
    lat_range: tuple[float, float],
    pixel_deg: float,
    *,
    lat_center: float | None = None,
) -> tuple[int, int]:
    """
    Calculates the bin counts (nx, ny) for projet_lonlat such that the pixels are kept square in their angular size not raw lon/lat degrees

    pixel_deg is what sets the true angular size per pixel
    lat_center defaults to the range's midpoint
    """
    lon0, lon1 = lon_range
    lat0, lat1 = lat_range
    if lat_center is None:
        lat_center = (lat0 + lat1) / 2.0
    aspect = sky_aspect(lat_center)

    nx = round((lon1 - lon0) / (pixel_deg * aspect))
    ny = round((lat1 - lat0) / pixel_deg)

    return nx, ny


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
