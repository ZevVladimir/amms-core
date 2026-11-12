"""
Define dealing with the dataset from Besla+2012 Model 2

This is a GADGET-3 run with legacy snapshots found in
/xdisk/gbesla/group/b12/lmc_smc_mw/model2/snaps/. Read-only comparison data

Reason for including in core is that this is a comparison simulation without the intent of re-running it again
so any projects that want to analyze it can pull from the core

Array functions are numpy arrays only
load(), snapshot_time_gyr() lazily import pygadgetreader
"""

from __future__ import annotations

import numpy as np

from amms.core.analysis.frames import Frame

H = 0.7  # in the GB12 simulations h=0.7 which is included in the pygadgetreader outputs
GADGET_TIME_TO_GYR = 0.9778  # 1 (kpc/h)/(km/s) = 0.9778 Gyr/h
KPC_PER_GYR_PER_KMS = 1.0227

N_LMC_INIT = 1_400_000
N_SMC_INIT = 414_000
N_TOT_INIT = N_LMC_INIT + N_SMC_INIT
# From Himansh SMC DM count is 10000 but is actually 14000

SNAP_PRESENT_DAY = 69

# Himansh computed LMC density center and bulk velocity as below
# Need to check this with my new framing methods
LMC_CENTER_069 = (-0.18, -37.28, -30.40)  # kpc
LMC_VCENTER_069 = (-81.28, -264.26, 248.83)  # km/s

# B12's MW was just a potential so assumed to be fixed at box origin for all snaps
# Raw positions from readsnap are galactocentric
# TODO confirm this from the paper
MW_CENTER = (0.0, 0.0, 0.0)  # kpc

# Position-angle reference reproducing Himansh Rathore's clouds_demo frame: the
# spherical polar basis (theta_hat, phi_hat, r_hat) at L_hat, so y' is the line
# of nodes. Matches his figures
# Deliberately NOT the amms default: ref . z_hat = -cos(theta), so it degenerates
# when the disk normal nears the box z-axis -- which is how our ICs are built.
PA_REFERENCE_CLOUDS_DEMO = (0.0, 0.0, -1.0)


def conventions() -> dict:
    """
    Unit conventions baked into any array this module returns
    Kept in every product's meta data for provenance
    """
    return {"units": "kpc, km/s, Msun, Gyr", "h": H, "gadget_time_to_gyr": GADGET_TIME_TO_GYR}


def to_kpc(pos: np.ndarray) -> np.ndarray:
    return np.asarray(pos, dtype=float) / H


def to_msun(mass: np.ndarray) -> np.ndarray:
    return np.asarray(mass, dtype=float) * 1e10 / H


def to_gyr(t: np.ndarray | float) -> np.ndarray:
    return np.asarray(t, dtype=float) * GADGET_TIME_TO_GYR / H


# map pygadgetreader fields -> (canonical name, converter).
# Most important: 'age' is pygadgetreader's name for formation TIME
_FIELDS = {
    "pos": ("pos_kpc", to_kpc),
    "vel": ("vel_kms", lambda v: np.asarray(v, dtype=float)),
    "mass": ("mass_msun", to_msun),
    "age": ("t_form_gyr", to_gyr),
}

# velocities don't need a conversion function since they are km/s with no h dependency


def load(
    snap, ptype: str, galaxy: str | None = None, fields=("pos", "vel", "mass")
) -> dict[str, np.ndarray]:
    """
    Loads in one particle type of a B12 snapshot using canonical units
    Passing galaxy=None keeps both the LMC and SMC (otherwise masked with galaxy_mask())
    No cuts made other than galaxy
    Pygadgetreader is imported lazily since it is B12-only
    """
    from pygadgetreader import readsnap

    snap = str(snap)
    pid = readsnap(snap, "pid", ptype)
    sel = slice(None) if galaxy is None else galaxy_mask(pid, galaxy)
    out = {"pid": pid[sel]}
    for f in fields:
        name, conv = _FIELDS[f]
        out[name] = conv(readsnap(snap, f, ptype)[sel])
    return out


def snapshot_time_gyr(snap) -> float:
    from pygadgetreader import readheader

    return float(to_gyr(readheader(str(snap), "time")))


def formed_in_run(t_form_gyr: np.ndarray) -> np.ndarray:
    """
    Returns False for ft==0 clock-reset stars
    Do not use these stars for SFH calculations
    """
    return np.asarray(t_form_gyr) > 0


def galaxy_frame(
    disk: dict[str, np.ndarray], galaxy: str, *, r_center: float = 10.0, r_axis: float = 10.0
) -> Frame:
    """
    Frame created from the galaxy's initial disk stars (there are not enough young stars to make the frame)
    Selection done by ID not position to keep consistent LMC/SMC assignment even during collision
    r_center=10 is needed since default r_init stops early due to the tidal tails (see b12.md, Frames)
    """
    m = galaxy_mask(disk["pid"], galaxy)
    return Frame.from_tracers(
        disk["pos_kpc"][m],
        disk["vel_kms"][m],
        disk["mass_msun"][m],
        r_center=r_center,
        r_axis=r_axis,
        reference=PA_REFERENCE_CLOUDS_DEMO,
        tracers=f"b12_{galaxy}_disk_stars",
    )


def parent_gas_id(pid: np.ndarray) -> np.ndarray:
    """
    Recover the parent gas particle ID of a newly formed star

    New-stars have a high flag bit.
    By clearing the most significant set bit you obtain the parent id
    Decode the whacky pids and return the indices belonging to the LMC. Credit to TJ Cox for writing the whacky aspect of this in IDL,
        which Himansh converted to python.
        Inputs:
            pids -> array of particle ids, including the whacky ones
            n_lmc_init -> total number of particles in the LMC initial condition
            n_smc_init -> total number of particles in the SMC initial condition

    I then implement this as vectorized integer artihmetic
    """
    pid = np.asarray(pid, dtype=np.int64)
    x = pid.copy()
    for s in (1, 2, 4, 8, 16, 32):
        x |= x >> s  # smear the top set bit down through all lower bits
    return pid & (x >> 1)


def galaxy_mask(pid: np.ndarray, galaxy: str) -> np.ndarray:
    """
    Creates a boolean mask selecting particles that belong to the LMC and those that belong to the SMC

    IDs 1 -> N_LMC_INIT are LMC then the next N_SMC_INIT are SMC
    New stars have IDs above N_TOT_INIT because of their flag bit which can be resolved using their parent gas particle

    This is specific to the GB12 initial conditions and setup
    """
    pid = np.asarray(pid, dtype=np.int64)
    resolved = np.where(pid > N_TOT_INIT, parent_gas_id(pid), pid)

    if galaxy == "lmc":
        return (resolved >= 1) & (resolved <= N_LMC_INIT)
    if galaxy == "smc":
        return (resolved > N_LMC_INIT) & (resolved <= N_TOT_INIT)
    raise ValueError(f"galaxy must be 'lmc' or 'smc', got{galaxy!r}")
