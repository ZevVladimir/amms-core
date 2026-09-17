"""
Renders the Map2D map objects produced from (src/amms/core/analysis/maps.py)
Labels and units come from the map not the caller
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm, Normalize

from amms.core.analysis.maps import Map2D

__all__ = ["panel_grid", "shared_norm", "show_map"]


def _finite_range(data: np.ndarray, log: bool) -> tuple[float, float] | tuple[None, None]:
    d = data[np.isfinite(data)]
    if log:
        d = d[d > 0]
    return (float(d.min()), float(d.max())) if d.size else (None, None)


def shared_norm(maps, *, log=True, min_counts=1, percentiles=None):
    """
    Creates one norm for multiple maps allowing for multiple panels to be compared

    percentiles=(1,99) clips outliers
    """
    pool = []
    for m in maps:
        d = m.masked(min_counts).ravel()
        d = d[np.isfinite(d)]
        pool.append(d[d > 0] if log else d)

    pool = np.concatenate(pool) if pool else np.array([])

    if not pool.size:
        return LogNorm() if log else Normalize()

    if percentiles is None:
        vmin, vmax = float(pool.min()), float(pool.max())
    else:
        vmin, vmax = (float(v) for v in np.percentile(pool, percentiles))

    return LogNorm(vmin=vmin, vmax=vmax) if log else Normalize(vmin=vmin, vmax=vmax)


def show_map(
    m: Map2D,
    ax: plt.Axes | None = None,
    *,
    norm=None,
    log: bool = True,
    min_counts: int = 1,
    cmap: str | None = None,
    vmin: float | None = None,
    vmax: float | None = None,
    cbar: bool = True,
    label: str | None = None,
    aspect: float | str = "equal",
):
    if ax is None:
        _, ax = plt.subplots(constrained_layout=True)

    data = m.masked(min_counts)

    # Caller-supplied norm allows for multiple panels to share the same scale
    if norm is None:
        lo, hi = _finite_range(data, log)
        vmin = lo if vmin is None else vmin
        vmax = hi if vmax is None else vmax
        norm = LogNorm(vmin=lo, vmax=hi) if log else Normalize(vmin=lo, vmax=hi)
    elif vmin is not None or vmax is not None:
        raise ValueError("pass either norm or vmin/vmax not both")

    # interpolation = "nearest" means that the map isn't smoothed like the default does
    # aspect handled below via set_box_aspect -- imshow's own aspect=<non-auto> shrinks the
    # Axes box via a path (Axes.apply_aspect) that make_axes_locatable's colorbar divider
    # doesn't track, leaving a gap between the image and the colorbar
    im = ax.imshow(
        data,
        origin="lower",
        extent=m.extent,
        norm=norm,
        cmap=cmap,
        aspect="auto",
        interpolation="nearest",
    )
    if aspect != "auto":
        x0, x1, y0, y1 = m.extent
        data_aspect = 1.0 if aspect == "equal" else float(aspect)
        ax.set_box_aspect(abs(y1 - y0) / abs(x1 - x0) * data_aspect)

    ax.set_xlabel(m.axis_labels[0] if m.axis_labels else f"{m.axes[0]} [kpc]")
    ax.set_ylabel(m.axis_labels[1] if m.axis_labels else f"{m.axes[1]} [kpc]")

    if m.invert_x:
        ax.invert_xaxis()
    if m.invert_y:
        ax.invert_yaxis()

    if cbar:
        cb = ax.figure.colorbar(im, ax=ax)
        cb.set_label(label if label is not None else f"{m.quantity} [{m.unit}]")
    return im


def panel_grid(
    maps: list[Map2D],
    *,
    ncols: int = 2,
    log: bool = True,
    min_counts: int = 1,
    percentiles: tuple[float, float] | None = None,
    share_norm: bool = True,
    titles: list[str] | None = None,
    **kw,
):
    """
    Creates a grid of maps

    share_norm forces one color scale across the panel
    """
    nrows = np.ceil(len(maps) / ncols)
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(4.2 * ncols, 4.0 * nrows), squeeze=False, constrained_layout=True
    )
    flat = axes.ravel()

    norm = None
    if share_norm:
        norm = shared_norm(maps, log=log, min_counts=min_counts, percentiles=percentiles)

    for i, m in enumerate(maps):
        im = show_map(
            m,
            flat[i],
            norm if share_norm else None,
            log=log,
            min_counts=min_counts,
            cbar=not share_norm,
            **kw,
        )
        if titles is not None:
            flat[i].set_title(titles[i])

    for ax in flat[len(maps) :]:
        ax.set_visible(False)

    if share_norm and maps:
        fig.colorbar(im, ax=axes, label=f"{maps[0].quantity} [{maps[0].unit}]")
    return fig, axes
