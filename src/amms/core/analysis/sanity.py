"""
Looks at per-snapshot invariants and retursn CheckResults (from amms.core.checks)

Arrays in, results out
Snapshot reading stays in driver until io/ is unfrozen
numpy only so analysis/ still imports in the legacy-gadget venv
"""

from __future__ import annotations

import numpy as np

from amms.core.checks import CheckResult, Status

__all__ = ["check_finite", "check_in_box", "check_unique_positions", "max_radius"]


def check_finite(name: str, arr: np.ndarray) -> CheckResult:
    """
    FAIL if any row has a NaN/inf
    Having a bad particle will mess up the entire tree
    """
    bad = ~np.isfinite(arr).reshape(len(arr), -1).all(axis=1)
    n = int(bad.sum())
    return CheckResult(name, Status.FAIL if n else Status.PASS, n, 0, "non-finite rows")


def check_in_box(name: str, pos: np.ndarray, box_size: float, *, margin: float) -> CheckResult:
    """
    Gas is always periodic (even with GRAVITY_NOT_PERIODIC)
    So a cell crossing a face reappears on the opposite side with the wrong gravity
    FAIL outside [0, box_size], WARN within margin of a face
    value is the smallest distance to a face, negative if outsid [units of pos]
    """
    d = float(np.min(np.minimum(pos, box_size - pos)))
    status = Status.FAIL if d < 0 else Status.WARN if d < margin else Status.PASS
    return CheckResult(name, status, d, margin, "min distance to a box face")


def check_unique_positions(
    name: str, pos: np.ndarray, *, on_duplicate: Status = Status.FAIL
) -> CheckResult:
    """
    value: number of particles sharing their position with another
    np.unique(axis=0) is a full sort, which requires a few copies of pos in memory
    """
    if len(pos) == 0:
        return CheckResult(name, Status.PASS, 0, 0, "no particles")
    _, cnt = np.unique(pos, axis=0, return_counts=True)
    n = int(cnt[cnt > 1].sum())
    return CheckResult(
        name, on_duplicate if n else Status.PASS, n, 0, f"max multiplicity {int(cnt.max())}"
    )


def max_radius(pos: np.ndarray, center: np.ndarray) -> float:
    return float(np.linalg.norm(pos - center, axis=1).max())
