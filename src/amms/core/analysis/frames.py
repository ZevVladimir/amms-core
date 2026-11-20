"""
Establishes the frames for galaxy-centric analysis

Everything is designed to only take numpy arrays and be simulation agnostic
Takes (N, 3) arrays in physical units -> Returns in physical units

Derive a Frame for initial disk stars and then apply that to young stars, gas, dark matter
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

__all__ = [
    "Frame",
    "RotStep",
    "angular_momentum_axis",
    "bulk_velocity",
    "compose",
    "face_on_basis",
    "face_on_basis_gram_schmidt",
    "face_on_steps",
    "rot_x",
    "rot_y",
    "rot_z",
    "shrinking_sphere_center",
    "translate",
]


def rot_x(angle: float) -> np.ndarray:
    """
    Provides a matrix to do an active rotation by angle (rad) about x
    """
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(angle: float) -> np.ndarray:
    """
    Provides a matrix to do an active rotation by angle (rad) about y
    """
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(angle: float) -> np.ndarray:
    """
    Provides a matrix to do an active rotation by angle (rad) about z

    rot_z(-alpha) @ R puts the in-plane direction at angle alpha (measured in R's frame) onto +x'
    """
    c, s = np.cos(angle), np.sin(angle)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


_ROT = {"x": rot_x, "y": rot_y, "z": rot_z}


@dataclass(frozen=True)
class RotStep:
    """
    Records one active rotation about an axis of the current frame

    Frame.rotation = step_n @ ... @ step_1 (to apply first step first apply it on the right)
    """

    axis: str  # "x" | "y" | "z"
    angle_deg: float
    purpose: str

    def matrix(self) -> np.ndarray:
        return _ROT[self.axis](np.radians(self.angle_deg))


def compose(steps) -> np.ndarray:
    R = np.eye(3)
    for s in steps:
        R = s.matrix() @ R
    return R


def face_on_steps(zhat, *, reference=(1.0, 0.0, 0.0)) -> tuple[RotStep, ...]:
    """
    Like face_on_basis_gram_schmidt() later on but with the rotation split into its three rotations
    with test_frames.py pinned to match the output
    """
    zhat = np.asarray(zhat, dtype=float)
    zhat = zhat / np.linalg.norm(zhat)
    ref = np.asarray(reference, dtype=float)
    ref = ref / np.linalg.norm(ref)

    # If the projected reference would be zero length
    if abs(float(ref @ zhat)) > 0.99:
        ref = np.eye(3)[int(np.argmin(np.abs(zhat)))]

    phi = np.arctan2(zhat[1], zhat[0])
    # Clip: since normalized vectors can have |z| = 1 + 1e-16 which would return nan with arccos
    theta = np.arccos(np.clip(zhat[2], -1.0, 1.0))
    r = rot_y(-theta) @ rot_z(-phi) @ ref
    alpha = np.arctan2(r[1], r[0])
    return (
        RotStep("z", -float(np.degrees(phi)), "bring the disk normal's azimuth onto the x-z plane"),
        RotStep("y", -float(np.degrees(theta)), "tilt the disk normal onto +z (face-on)"),
        RotStep("z", -float(np.degrees(alpha)), "position angle: projected reference onto +x"),
    )


def face_on_basis(zhat, *, reference=(1.0, 0.0, 0.0)) -> np.ndarray:
    return compose(face_on_steps(zhat, reference=reference))


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


def face_on_basis_gram_schmidt(
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
    rot_steps: tuple[RotStep, ...] = ()
    pa_convention: str = ""

    def __post_init__(self) -> None:
        # Convert lists (from metadata file or literal) to arrays
        for name in ("center", "v_center", "rotation"):
            object.__setattr__(self, name, np.asarray(getattr(self, name), dtype=float))
        object.__setattr__(self, "rot_steps", tuple(self.rot_steps))
        # rot_steps documents the rotation
        if self.rot_steps and not np.allclose(compose(self.rot_steps), self.rotation, atol=1e-10):
            raise ValueError("rot_steps do not compose to rotation")

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
        pa_convention: str = "sim_x",
    ) -> Frame:
        center = shrinking_sphere_center(pos, mass, r_init=r_center)
        v_center = bulk_velocity(pos, vel, mass, center, r_max=r_vel)
        zhat = angular_momentum_axis(pos, vel, mass, center=center, v_center=v_center, r_max=r_axis)

        if pa_convention == "sim_x" and not np.allclose(reference, (1.0, 0.0, 0.0)):
            # default label would silently mislabel a non-default reference
            raise ValueError("pass pa_convention naming the non-default reference")
        steps = face_on_steps(zhat, reference=reference)
        return cls(
            center,
            v_center,
            compose(steps),
            tracers=tracers,
            r_axis=r_axis,
            rot_steps=steps,
            pa_convention=pa_convention,
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

    def rotated_z(
        self, alpha: float, *, purpose: str, pa_convention: str, tracers: str | None = None
    ) -> Frame:
        """
        Returns a new Frame rotated about z' so that the direction at angle alpha (rad, in this frame) lands on +x'

        purpose is required: every rotation in a product's meta says why it is there
        Center and v_center remain unchanged
        Only the position angle moves
        """
        step = RotStep("z", -float(np.degrees(alpha)), purpose)
        return replace(
            self,
            rotation=step.matrix() @ self.rotation,
            rot_steps=(*self.rot_steps, step) if self.rot_steps else (),
            pa_convention=pa_convention,
            tracers=self.tracers if tracers is None else tracers,
        )

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
            "pa_convention": self.pa_convention,
            "rot_steps": [
                {"axis": s.axis, "angle_deg": float(s.angle_deg), "purpose": s.purpose}
                for s in self.rot_steps
            ],
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
