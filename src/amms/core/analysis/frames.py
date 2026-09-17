"""
Establishes the frames for galaxy-centric analysis

Everything is designed to only take numpy arrays and be simulation agnostic
Takes (N, 3) arrays in physical units -> Returns in physical units

Derive a Frame for initial disk stars and then apply that to young stars, gas, dark matter
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "Frame",
    "angular_momentum_axis",
    "bulk_velocity",
    "face_on_basis",
    "shrinking_sphere_center",
    "translate",
]


def shrinking_sphere_center(
    pos: np.ndarray,
    mass: np.ndarray | None = None,
    *,
    r_init: float | None = None,
    shrink: float = 0.9,
    n_min: int = 100,
    tol: float = 0.001,
    patience: int = 2,
) -> np.ndarray:
    """
    Determine the density center which is described in Rathore+2025b which implements the method from Power+2003
    1. Obtain approximate center of mass using mass weighted average position of the stars
    2. Define a sphere of radius r_init centered on this approximate COM
    3. Compute the center of of mass of stars that reside in the sphere
    4. Shrink radius of the sphere by shrink (0.9 is 10%) and recompute new COM
    5. Repeat 3-4 until convergence criterion is met. COM doesn't change by more than tol kpc between patience successive iterations or below n_min

    Returns the last center based on convergence criterion
    """
    pos = np.asarray(pos, dtype=float)
    mass = np.ones(len(pos)) if mass is None else np.asarray(mass, dtype=float)

    # Calculate initial approximate COM
    center = np.average(pos, axis=0, weights=mass)

    # Determine what particles are within a sphere of radius r_init centered on the approximate COM
    d = np.linalg.norm(pos - center, axis=1)
    radius = float(d.max() if r_init is None else r_init)

    # Keep shrinking the sphere until the number of particles remaining is below n_min or (excepting the initial iteration) the COM
    # doesn't change by more than tol kpc in patience iterations
    settled = 0
    while True:
        inside = d <= radius
        if int(inside.sum()) < n_min:
            return center

        moved = np.average(pos[inside], axis=0, weights=mass[inside])
        step = float(np.linalg.norm(moved - center))
        center = moved

        # Sphere with all tracers re-averages the sample reproducing the initial center. So ignore for first iteration
        settled = settled + 1 if (step < tol and not inside.all()) else 0
        if settled >= patience:
            return center

        d = np.linalg.norm(pos - center, axis=1)
        radius *= shrink


def bulk_velocity(
    pos: np.ndarray,
    vel: np.ndarray,
    mass: np.ndarray | None,
    center: np.ndarray,
    *,
    r_max: float = 5.0,
) -> np.ndarray:
    """
    Calculates the mass-weighted mean velocity of tracers within r_max of the center
    """
    pos = np.asarray(pos, dtype=float)
    vel = np.asarray(vel, dtype=float)
    center = np.asarray(center, dtype=float)

    inside = np.linalg.norm(pos - center, axis=1) <= r_max
    if not inside.any():
        raise ValueError(f"No tracers found within r_max={r_max} of the center")

    w = None if mass is None else np.asarray(mass, dtype=float)[inside]
    return np.average(vel[inside], axis=0, weights=w)


def angular_momentum_axis(
    pos: np.ndarray,
    vel: np.ndarray,
    mass: np.ndarray | None = None,
    *,
    center: np.ndarray | None = None,
    v_center: np.ndarray | None = None,
    r_max: float = 10.0,
) -> np.ndarray:
    """
    Calculates the unit vector along the net angular momentum of the tracers within r_max

    r_max excludes disturbed outskirts where angular momentum isn't determined by the disk
    """
    pos = np.asarray(pos, dtype=float)
    vel = np.asarray(vel, dtype=float)

    if center is not None:
        pos = pos - np.asarray(center, dtype=float)
    if v_center is not None:
        vel = vel - np.asarray(v_center, dtype=float)

    inside = np.linalg.norm(pos, axis=1) <= r_max
    if not inside.any():
        raise ValueError(f"no tracers found within r_max={r_max}")

    # calculate angular momentum per tracer and mass weight it if mass is provided
    j = np.cross(pos[inside], vel[inside])
    if mass is not None:
        j = j * np.asarray(mass, dtype=float)[inside, None]

    total = j.sum(axis=0)
    norm = float(np.linalg.norm(total))
    if norm == 0.0:
        raise ValueError("net angular momentum is zero; no axis is defined")
    return total / norm


def face_on_basis(
    zhat: np.ndarray,
    *,
    reference: np.ndarray = (1.0, 0.0, 0.0),
) -> np.ndarray:
    """
    Create a rotation matrix with rows (x', y', z') with z' along zhat

    Use Gram-Schmidt method

    Face-on is defined up to a rotation about z' so the reference vector passed fixes the position angle

    Convention: simulation x-axis is projected into the disk plane so that a time series stays oriented
    """
    zhat = np.asarray(zhat, dtype=float)
    zhat = zhat / np.linalg.norm(zhat)

    ref = np.asarray(reference, dtype=float)
    ref = ref / np.linalg.norm(ref)

    # This guard only works when ref is normalized such that ref @ zhat becomes cos(angle between the two)
    if abs(float(ref @ zhat)) > 0.99:
        # if this is true then degenerate and fall back to which simulation axis is least aligned with the disk's normal
        ref = np.eye(3)[int(np.argmin(np.abs(zhat)))]

    xhat = ref - float(ref @ zhat) * zhat
    xhat = xhat / np.linalg.norm(xhat)

    # Don't have to repeat gram-schmidt since only looking for 3 vectors and cross product guarantees a third orthogonal vector since xhat, zhat are already orthogonal
    yhat = np.cross(zhat, xhat)
    return np.stack([xhat, yhat, zhat])


@dataclass(frozen=True, eq=False)
class Frame:
    """
    Galaxy-centric frame: first translate, boost, then rotate

    Make sure to rotate last otherwise the center offset is rotated as well

    Dont have a generated __eq__ function since it raises on ambiguous truth values rather than compare
    """

    center: np.ndarray
    v_center: np.ndarray
    rotation: np.ndarray
    tracers: str = ""
    r_axis: float | None = None  # The r_max used for the angular momentum axis

    def __post_init__(self) -> None:
        # Convert lists (from metadata file or literal) to arrays
        for name in ("center", "v_center", "rotation"):
            object.__setattr__(self, name, np.asarray(getattr(self, name), dtype=float))

    @classmethod
    def from_tracers(
        cls,
        pos: np.ndarray,
        vel: np.ndarray,
        mass: np.ndarray | None = None,
        *,
        r_center: float = 10.0,
        r_vel: float = 5.0,
        r_axis: float = 10.0,
        reference: np.ndarray = (1.0, 0.0, 0.0),
        tracers: str = "",
    ) -> Frame:
        center = shrinking_sphere_center(pos, mass, r_init=r_center)
        v_center = bulk_velocity(pos, vel, mass, center, r_max=r_vel)
        zhat = angular_momentum_axis(pos, vel, mass, center=center, v_center=v_center, r_max=r_axis)

        return cls(
            center,
            v_center,
            face_on_basis(zhat, reference=reference),
            tracers=tracers,
            r_axis=r_axis,
        )

    @classmethod
    def translation(
        cls,
        current_center: np.ndarray,
        target_center: np.ndarray,
        *,
        rotation: np.ndarray | None = None,
        tracers: str = "",
    ) -> Frame:
        """
        Builds a frame that maps the current_center to target_center under .positions() with no velocity change

        Pass rotation to compose with a previously derived orientation instead of leaving it as the identity matrix
        """
        current_center = np.asarray(current_center, dtype=float)
        target_center = np.asarray(target_center, dtype=float)
        rot = np.eye(3) if rotation is None else np.asarray(rotation, dtype=float)

        return cls(current_center - target_center, np.zeros(3), rot, tracers=tracers)

    def positions(self, pos: np.ndarray) -> np.ndarray:
        # Returns the input positions with the Frame's corrections
        return translate(pos, -self.center) @ self.rotation.T

    def velocities(self, vel: np.ndarray) -> np.ndarray:
        # Returns the input velocities with the Frame's corrections
        return (np.asarray(vel, dtype=float) - self.v_center) @ self.rotation.T

    def to_dict(self) -> dict:
        """
        Return plain json-able types for Map2D to be able to record what frame it was made in
        """
        return {
            "center": [float(v) for v in self.center],
            "v_center": [float(v) for v in self.v_center],
            "rotation": [[float(v) for v in row] for row in self.rotation],
            "tracers": self.tracers,
            "r_axis": self.r_axis,
        }


def translate(pos: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """
    Shift the given positions by a constant offset

    offset = target_center - current center
    allows for the placement of a cloud with current_center on target_center
    """
    pos = np.asarray(pos, dtype=float)
    offset = np.asarray(offset, dtype=float)

    return pos + offset
