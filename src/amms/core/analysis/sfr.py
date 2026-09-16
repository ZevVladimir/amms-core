"""
Star formation rate estimators

Only does the physics definitions displaying this as a map is handled by src/amms/core/analysis/maps.py

Two methods:
    from_young_stars    the Sigma_SFR averaged over the last dt. Uses star particle masses and ages. Simulation just needs to record formation times
    from_gas            the instanteous rate carried by gas cells. Only available for AREPO+SMUGGLE simulations that have gas.

DIFFERENT results from the two methods
"""

from __future__ import annotations

import numpy as np

from amms.core.analysis.maps import Map2D, project_lonlat, project_map

__all__ = [
    "SFR_UNIT",
    "SFR_UNIT_SKY",
    "sfh",
    "sfr_map_from_gas",
    "sfr_map_from_young_stars",
    "sfr_sky_map_from_young_stars",
]

SFR_UNIT = "Msun/yr/kpc2"
SFR_UNIT_SKY = "Msun/yr/deg2"


def sfr_sky_map_from_young_stars(
    lon: np.ndarray,
    lat: np.ndarray,
    mass: np.ndarray,
    age: np.ndarray,
    *,
    dt: float = 0.1,
    lon_range: tuple[float, float] = (-180.0, 180.0),
    lat_range: tuple[float, float] = (-90.0, 90.0),
    bins: int | tuple[int, int] = 64,
    axis_labels: tuple[str, str] = ("lon [deg]", "lat [deg]"),
    invert_x: bool = True,
    invert_y: bool = False,
    meta: dict | None = None,
) -> Map2D:
    """
    Calculates the Sigma_SFR from young star particles projected onto a sky frame (RA/Dec, Glaactic l/b, ...)

    Same method as sfr_map_from_young_stars but with lon/lat instead of cartesian pos+axes projection

    To get lon/lat use amms.core.analysis.sky or another frame conversion

    per_area is deg^2 not kpc^2
    """
    age = np.asarray(age, dtype=float)
    young = (age >= 0.0) & (age < dt)

    rate = np.asarray(mass, dtype=float)[young] / (dt * 1e9)  # Msun / yr

    return project_lonlat(
        np.asarray(lon, dtype=float)[young],
        np.asarray(lat, dtype=float)[young],
        values=rate,
        lon_range=lon_range,
        lat_range=lat_range,
        bins=bins,
        reduce="sum",
        per_area=True,
        quantity="sigma_sfr",
        unit=SFR_UNIT_SKY,
        axis_labels=axis_labels,
        invert_x=invert_x,
        invert_y=invert_y,
        meta={
            **(meta or {}),
            "estimator": "young_stars",
            "dt_gyr": float(dt),
            "n_young": int(young.sum()),
        },
    )


def sfr_map_from_young_stars(
    pos: np.ndarray,
    mass: np.ndarray,
    age: np.ndarray,
    *,
    dt: float = 0.1,
    axes: str = "xy",
    extent: float | tuple[float, float, float, float] = 15.0,
    bins: int | tuple[int, int] = 64,
    meta: dict | None = None,
) -> Map2D:
    """
    Calculates the Sigma_SFR from star particles that are younger than dt

    pos in kpc in the frame desired
    mass in Msun
    age in Gyr
    dt in Gyr

    Result in Msun / yr / kpc^2

    Mass passed is the mass at snapshot time not at formation which due to feedback would be an underestimate of the rate worth checking
    """
    age = np.asarray(age, dtype=float)
    # Keep stars formed marginally past snapshot time which can arise from float round off
    young = (age >= 0.0) & (age < dt)

    rate = np.asarray(mass, dtype=float)[young] / (dt * 1e9)  # Msun / yr

    return project_map(
        np.asarray(pos, dtype=float)[young],
        values=rate,
        axes=axes,
        extent=extent,
        bins=bins,
        reduce="sum",
        per_area=True,
        quantity="sigma_sfr",
        unit=SFR_UNIT,
        meta={
            **(meta or {}),
            "estimator": "young_stars",
            "dt_gyr": float(dt),
            "n_young": int(young.sum()),
        },
    )


def sfr_map_from_gas(
    pos: np.ndarray,
    sfr: np.ndarray,
    *,
    axes: str = "xy",
    extent: float | tuple[float, float, float, float] = 15.0,
    bins: int | tuple[int, int] = 64,
    meta: dict | None = None,
) -> Map2D:
    """
    The Sigma_SFR from the per-cell instantaneous rate (AREPO StarFormationRate)

    Assumes sfr is Msun/yr per cell need to check against the run's specific unit system
    """
    return project_map(
        pos,
        values=sfr,
        axes=axes,
        extent=extent,
        bins=bins,
        reduce="sum",
        per_area=True,
        quantity="sigma_sfr",
        unit=SFR_UNIT,
        meta={**(meta or {}), "estimator": "gas_instantaneous"},
    )


def sfh(
    age: np.ndarray,
    mass: np.ndarray,
    *,
    bins: int | np.ndarray = 20,
    range: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Star formation history: (bin edges in Gyr, Msun/yr in each bin)

    Same physics as the map but with one less dimension
    """
    age = np.asarray(age, dtype=float)
    mass = np.asarray(mass, dtype=float)
    total, edges = np.histogram(
        age,
        bins=bins,
        range=range,
        weights=mass,
    )

    return edges, total / (np.diff(edges) * 1e9)
