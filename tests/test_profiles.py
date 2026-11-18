"""
Known-answer tests for analysis/profiles.py: analytic models, the epicyclic frequency for
rotation curves with closed-form kappa, and the mass-weighted statistics the IC plots rely on
(gridded ICs carry many near-massless background cells that must not drive count statistics).
"""

import numpy as np
import pytest

from amms.core.analysis import profiles as pr

RNG = np.random.default_rng(42)


def _hernquist_sample(n, a):
    # Inverse of M(<r)/M = r^2 / (r + a)^2
    s = np.sqrt(RNG.random(n))
    return a * s / (1 - s)


def test_hernquist_density_integrates_to_mass():
    r = np.geomspace(1e-6, 1e6, 200_001)
    m = np.trapezoid(4 * np.pi * r**2 * pr.hernquist_density(r, 2.5, 3.0), r)
    assert m == pytest.approx(2.5, rel=1e-4)


def test_shell_density_recovers_hernquist():
    n, mass, a = 400_000, 1.0, 1.0
    r = _hernquist_sample(n, a)
    edges = np.geomspace(0.1, 10, 11)
    got = pr.shell_density(r, np.full(n, mass / n), edges)
    # Exact shell mass from M(<r) = M r^2/(r+a)^2: a centre-point comparison is ~8% off for
    # bins this wide on a steep profile, which would hide a real error of the same size
    enc = mass * edges**2 / (edges + a) ** 2
    want = np.diff(enc) / (4 / 3 * np.pi * np.diff(edges**3))
    n_shell = n * np.diff(enc) / mass
    assert np.all(np.abs(got / want - 1) < 4 / np.sqrt(n_shell))  # 4 sigma Poisson per shell


def test_exponential_surface_density_integrates_to_mass():
    R = np.linspace(0, 60, 600_001)
    m = np.trapezoid(2 * np.pi * R * pr.exponential_surface_density(R, 0.7, 1.5), R)
    assert m == pytest.approx(0.7, rel=1e-6)


def test_annulus_density_uniform_disk():
    n = 200_000
    R = np.sqrt(RNG.random(n))  # uniform in area, radius 1
    got = pr.annulus_density(R, np.full(n, 1.0 / n), np.linspace(0, 1, 5))
    np.testing.assert_allclose(got, 1 / np.pi, rtol=0.02)


def test_kappa_flat_curve():
    R = np.linspace(1, 10, 91)
    k = pr.kappa(R, np.full_like(R, 200.0**2))
    np.testing.assert_allclose(k, np.sqrt(2) * 200 / R, rtol=1e-12)


def test_kappa_solid_body():
    omega = 3.0
    R = np.linspace(0.5, 5, 46)
    k = pr.kappa(R, (omega * R) ** 2)
    # np.gradient is exact for a quadratic only at interior (central-difference) points
    np.testing.assert_allclose(k[1:-1], 2 * omega, rtol=1e-12)


def test_vc_enclosed_point_mass():
    G, M = 43007.1, 0.01
    r_eval = np.array([0.5, 1.0, 4.0])
    vc = pr.vc_enclosed(np.array([0.0]), np.array([M]), r_eval, G)
    np.testing.assert_allclose(vc, np.sqrt(G * M / r_eval))


def test_vc_enclosed_counts_only_interior_mass():
    vc = pr.vc_enclosed(np.array([1.0, 3.0]), np.array([1.0, 1.0]), np.array([0.5, 2.0, 3.0]), 1.0)
    np.testing.assert_allclose(vc, [0.0, np.sqrt(1 / 2), np.sqrt(2 / 3)])  # r == 3 is enclosed


def test_sech2_median_matches_sample():
    z0 = 0.3
    z = z0 * np.arctanh(2 * RNG.random(400_000) - 1)  # inverse CDF of sech^2(z/z0)
    assert np.median(np.abs(z)) == pytest.approx(pr.SECH2_MEDIAN * z0, rel=0.01)


def test_cylindrical_solid_rotation_all_quadrants():
    # Pins arctan2-free projection: v_phi > 0 everywhere for prograde rotation, including x < 0
    omega = 2.0
    pos = RNG.normal(size=(1000, 3))
    vel = omega * np.column_stack([-pos[:, 1], pos[:, 0], np.zeros(len(pos))])
    R, v_R, v_phi = pr.cylindrical(pos, vel)
    np.testing.assert_allclose(R, np.hypot(pos[:, 0], pos[:, 1]))
    np.testing.assert_allclose(v_R, 0, atol=1e-12)
    np.testing.assert_allclose(v_phi, omega * R)


def test_binned_weighted_median_ignores_massless_cells():
    # 10 real cells at ~1, 1000 background cells at 100 with 1e-6 the mass
    x = np.full(1010, 0.5)
    v = np.r_[np.linspace(0.9, 1.1, 10), np.full(1000, 100.0)]
    w = np.r_[np.ones(10), np.full(1000, 1e-6)]
    assert 0.9 <= pr.binned(x, v, np.array([0, 1]), stat="median", weights=w)[0] <= 1.1
    assert pr.binned(x, v, np.array([0, 1]), stat="median")[0] == 100.0  # unweighted is fooled


def test_binned_mean_std_match_numpy_for_equal_weights():
    x = RNG.random(500)
    v = RNG.normal(3, 2, 500)
    edges = np.array([0, 0.5, 1])
    sel = x < 0.5
    assert pr.binned(x, v, edges, stat="mean")[0] == pytest.approx(v[sel].mean())
    assert pr.binned(x, v, edges, stat="std")[1] == pytest.approx(v[~sel].std())


def test_binned_sparse_bins_are_nan():
    out = pr.binned(
        np.array([0.1, 0.2, 0.7]), np.array([1.0, 2.0, 3.0]), np.array([0, 0.5, 1]), stat="mean"
    )
    assert out[0] == pytest.approx(1.5)
    assert np.isnan(out[1])  # one particle is not a statistic


def test_binned_unknown_stat_raises():
    with pytest.raises(ValueError, match="unknown stat"):
        pr.binned(np.zeros(3), np.zeros(3), np.array([0, 1]), stat="mode")


def test_toomre_constants():
    # Q = 1 at marginal stability: sigma_R = 3.36 G Sigma / kappa (stars), c_s = pi G Sigma / kappa (gas)
    assert pr.toomre_q_stars(3.36, 1.0, 1.0, 1.0) == pytest.approx(1.0)
    assert pr.toomre_q_gas(np.pi, 1.0, 1.0, 1.0) == pytest.approx(1.0)
