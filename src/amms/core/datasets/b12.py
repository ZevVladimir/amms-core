"""
Define dealing with the dataset from Besla+2012 Model 2

This is a GADGET-3 run with legacy snapshots found in
/xdisk/gbesla/group/b12/lmc_smc_mw/model2/snaps/. Read-only comparison data

Reason for including in core is that this is a comparison simulation without the intent of re-running it again
so any projects that want to analyze it can pull from the core

Does not use pygadgetreader and functions only take in numpy arrays
"""

from __future__ import annotations

import numpy as np

H = 0.7  # in the GB12 simulations h=0.7 which is included in the pygadgetreader outputs
GADGET_TIME_TO_GYR = 0.97  # kpc/Gyr <-> km/s conversion

N_LMC_INIT = 1_400_000
N_SMC_INIT = 414_000
N_TOT_INIT = N_LMC_INIT + N_SMC_INIT
# From Himansh SMC DM count is 10000 but is actually 14000

SNAP_PRESENT_DAY = 69

# Himansh computed LMC density center and bulk velocity as below
# Need to check this with my new framing methods
LMC_CENTER_069 = (-0.18, -37.28, -30.40)  # kpc
LMC_VCENTER_069 = (-81.28, -264.26, 248.83)  # km/s


def to_kpc(pos: np.ndarray) -> np.ndarray:
    return np.asarray(pos, dtype=float) / H


def to_msun(mass: np.ndarray) -> np.ndarray:
    return np.asarray(mass, dtype=float) * 1e10 / H


def to_gyr(t: np.ndarray | float) -> np.ndarray:
    return np.asarray(t, dtype=float) * GADGET_TIME_TO_GYR / H


# velocities don't need a conversion function since they are km/s with no h dependency


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
