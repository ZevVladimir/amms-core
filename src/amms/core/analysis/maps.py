"""
Create binned 2-D maps of particles and their cell quantities and their serialization

Works from the npz products done with the compute which a notebook then loads and plots
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

__all__ = ["Map2D", "project_map"]

_AXES = {"xy": (0, 1), "xz": (0, 2), "yz": (1, 2)}


@dataclass(frozen=True, eq=False)
class Map2D:
    """
    Holds a binned 2-D map and everything to interpret it

    values are indexed with [row, col] == [y, x] as in imshow()
    counts are the raw particle count per pixel
    """

    values: np.ndarray
    counts: np.ndarray
    extent: tuple[float, float, float, float]  # used for plot axes
    axes: str
    quantity: str
    unit: str
    meta: dict = field(default_factory=dict)

    @property
    def pixel_area(self) -> float:
        x0, x1, y0, y1 = self.extent
        ny, nx = self.values.shape
        return abs(x1 - x0) * abs(y1 - y0) / (nx * ny)

    def masked(self, min_counts: int = 1) -> np.ndarray:
        """
        Pixels that are below the min_counts threshold are set to nan (rendered empty)
        """
        return np.where(self.counts >= min_counts, self.values, np.nan)

    def save(self, path: str | Path) -> Path:
        """
        Write the npz
        Meta goes through json so load() can refuse pickles
        """
        np.savez_compressed(
            path,
            values=self.values,
            counts=self.counts,
            extent=np.asarray(self.extent, dtype=float),
            axes=self.axes,
            quantity=self.quantity,
            unit=self.unit,
            meta=json.dumps(self.meta),
        )

        return Path(str(path) + "" if str(path).endswith(".npz") else ".npz")

    @classmethod
    def load(cls, path: str | Path) -> Map2D:
        # all_pickle=False blocks pickled arrays as they are not consistent across versions and are more vulnerable
        with np.load(path, allow_pickle=False) as f:
            return cls(
                values=f["values"],
                counts=f["counts"],
                extent=tuple(float(v) for v in f["extent"]),
                axes=str(f["axes"].item()),
                quantity=str(f["quantity"].item()),
                unit=str(f["unit"].item()),
                meta=json.loads(str(f["meta"].item())),
            )


def project_map(
    pos: np.ndarray,
    values: np.ndarray | None = None,
    *,
    weights: np.ndarray | None = None,
    axes: str = "xy",
    extent: float | tuple[float, float, float, float] = 15.0,
    bins: int | tuple[int, int] = 64,
    reduce: str = "sum",
    per_area: bool = False,
    quantity: str = "",
    unit: str = "",
    meta: dict | None = None,
) -> Map2D:
    """
    Bin input values onto a 2-D grid of a coordinate projection

    reduce options:
        - reduce="sum"  total of `values` per pixel (pass mass; with per_area=True obtain surface density) `values=None` gives raw counts
        - reduce="mean" weighted mean of `values` (pass weights=mass, values=v_los)
        - reduce="std"  weighted standard deviation of `values` (dispersion maps)

    extent can be half-width which will be expanded to be the same length in each direction (-h, h, -h, h)
    """
    if axes not in _AXES:
        raise ValueError(f"axes must be one of {sorted(_AXES)}, got {axes!r}")
    ix, iy = _AXES[axes]

    pos = np.asarray(pos, dtype=float)
    if np.isscalar(extent):
        h = float(extent)
        extent = (-h, h, -h, h)
    x0, x1, y0, y1 = (float(v) for v in extent)
    rng = ((x0, x1), (y0, y1))

    x, y = pos[:, ix], pos[:, iy]

    counts, xe, ye = np.histogram2d(x, y, bins=bins, range=rng)

    if reduce == "sum":
        w = None if values is None else np.asarray(values, dtype=float)
        out, _, _ = np.histogram2d(x, y, bins=bins, range=rng, weights=w)
    elif reduce in ("mean", "std"):
        if values is None:
            raise ValueError(f"reduce={reduce!r} requires `values`")

        v = np.asarray(values, dtype=float)
        w = np.ones_like(v) if weights is None else np.asarray(weights, dtype=float)

        wsum, _, _ = np.histogram2d(x, y, bins=bins, range=rng, weights=w)
        wv, _, _ = np.histogram2d(x, y, bins=bins, range=rng, weights=w * v)

        with np.errstate(invalid="ignore", divide="ignore"):
            mean = wv / wsum
            if reduce == "mean":
                out = mean
            else:
                wv2, _, _ = np.histogram2d(x, y, bins=bins, range=rng, weights=w * v * v)
                # Var = <v^2> - <v>^2 clipped at 0
                out = np.sqrt(np.clip(wv2 / wsum - mean**2, 0.0, None))
    else:
        raise ValueError(f"unknown reduce={reduce!r}")

    if per_area:
        if reduce != "sum":
            raise ValueError("per_area only means anything with reduce='sum'")
        out = out / ((xe[1] - xe[0]) * (ye[1] - ye[0]))

    # histogram2d returns [nx, ny] but imshow expects [ny, nx]
    # Do the transpose here so that it is consistent for imshow and it is the odd case to reverse the transpose
    return Map2D(
        values=out.T,
        counts=counts.T,
        extent=(x0, x1, y0, y1),
        axes=axes,
        quantity=quantity,
        unit=unit,
        meta=dict(meta or {}),
    )
