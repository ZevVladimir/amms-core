"""
Pins every branch of the per-snapshot invariants in amms.core.analysis.sanity.

Box geometry mirrors the edw1 run (BoxSize 200, galaxy at the centre) so values read like the
real check output. Margin 10 is the driver default, not a physical number.
"""

import numpy as np

from amms.core.analysis import sanity
from amms.core.checks import Status

BOX = 200.0
MARGIN = 10.0


def test_finite_pass():
    r = sanity.check_finite("finite_gas", np.full((4, 3), 100.0))
    assert (r.status, r.value) == (Status.PASS, 0)


def test_finite_counts_rows_not_elements():
    pos = np.full((4, 3), 100.0)
    pos[1, :] = np.nan  # three bad elements, one bad particle
    pos[3, 2] = np.inf
    r = sanity.check_finite("finite_gas", pos)
    assert (r.status, r.value) == (Status.FAIL, 2)


def test_finite_accepts_per_particle_scalars():
    # Masses / densities are 1-D; the reshape must treat each element as a row
    r = sanity.check_finite("finite_mass", np.array([1.0, np.nan, 2.0]))
    assert (r.status, r.value) == (Status.FAIL, 1)


def test_in_box_pass_well_inside():
    r = sanity.check_in_box("gas_in_box", np.array([[100.0, 100.0, 100.0]]), BOX, margin=MARGIN)
    assert (r.status, r.value) == (Status.PASS, 100.0)


def test_in_box_warn_within_margin():
    pos = np.array([[100.0, 100.0, 100.0], [100.0, 5.0, 100.0]])
    r = sanity.check_in_box("gas_in_box", pos, BOX, margin=MARGIN)
    assert (r.status, r.value) == (Status.WARN, 5.0)


def test_in_box_fail_below_lower_face():
    r = sanity.check_in_box("gas_in_box", np.array([[-1.0, 100.0, 100.0]]), BOX, margin=MARGIN)
    assert (r.status, r.value) == (Status.FAIL, -1.0)


def test_in_box_fail_past_upper_face():
    # The upper face is the one a "pos >= 0" check misses
    r = sanity.check_in_box("gas_in_box", np.array([[100.0, 100.0, 201.0]]), BOX, margin=MARGIN)
    assert (r.status, r.value) == (Status.FAIL, -1.0)


def test_unique_positions_pass():
    r = sanity.check_unique_positions("unique_gas", np.array([[1.0, 2.0, 3.0], [1.0, 2.0, 4.0]]))
    assert (r.status, r.value) == (Status.PASS, 0)


def test_unique_positions_duplicate_fails_by_default():
    pos = np.array([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [1.0, 2.0, 3.0], [5.0, 5.0, 5.0]])
    r = sanity.check_unique_positions("unique_gas", pos)
    assert (r.status, r.value) == (Status.FAIL, 3)  # counts every particle at the shared spot
    assert "max multiplicity 3" in r.detail


def test_unique_positions_duplicate_downgraded():
    # Cross-type check: a spawned star on its parent cell is expected, so the driver passes WARN
    pos = np.array([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
    r = sanity.check_unique_positions("unique_all", pos, on_duplicate=Status.WARN)
    assert (r.status, r.value) == (Status.WARN, 2)


def test_unique_positions_empty():
    r = sanity.check_unique_positions("unique_gas", np.empty((0, 3)))
    assert (r.status, r.value) == (Status.PASS, 0)


def test_max_radius_known_answer():
    pos = np.array([[103.0, 104.0, 100.0], [101.0, 100.0, 100.0]])
    assert sanity.max_radius(pos, np.full(3, 100.0)) == 5.0
