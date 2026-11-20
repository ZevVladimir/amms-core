"""
Pins for analysis/frames.py rotations, written before the named-matrix rewrite of
face_on_basis (.claude/rules/maps.md). The golden matrices are today's outputs: the rewrite
must reproduce them, which is what keeps every existing product's frame meaning unchanged.
"""

import numpy as np
import pytest

from amms.core.analysis import frames as fr

RNG = np.random.default_rng(7)
EZ = np.array([0.0, 0.0, 1.0])
REFERENCES = [(1.0, 0.0, 0.0), (0.0, 0.0, -1.0)]  # default, B12 clouds_demo


def _random_normals(n):
    z = RNG.normal(size=(n, 3))
    return z / np.linalg.norm(z, axis=1, keepdims=True)


# --- golden pins: face_on_basis output at 2026-11-19 (pre-rewrite) ---

GOLDEN = [
    (
        (0.3, -0.5, 0.8),
        (1.0, 0.0, 0.0),
        [
            [0.9529760045804524, 0.16061393335625598, -0.25698229337000966],
            [0.0, 0.847998304005088, 0.5299989400031799],
            [0.3030457633656632, -0.5050762722761053, 0.8081220356417687],
        ],
    ),
    (
        (0.3, -0.5, 0.8),
        (0.0, 0.0, -1.0),
        [
            [0.4157753572051423, -0.6929589286752371, -0.5890150893739515],
            [0.8574929257125442, 0.5144957554275266, 0.0],
            [0.3030457633656632, -0.5050762722761053, 0.8081220356417687],
        ],
    ),
    # |ref . zhat| > 0.99 -> fallback to the axis least aligned with zhat (x here)
    (
        (0.0, 0.05, 0.999),
        (0.0, 0.0, -1.0),
        [
            [1.0, 0.0, 0.0],
            [0.0, 0.9987498444920088, -0.04998747970430475],
            [0.0, 0.04998747970430475, 0.9987498444920088],
        ],
    ),
]


@pytest.mark.parametrize(("zhat", "ref", "expected"), GOLDEN)
def test_face_on_basis_golden(zhat, ref, expected):
    got = fr.face_on_basis(np.array(zhat), reference=ref)
    np.testing.assert_allclose(got, expected, atol=1e-14)


# --- properties of the convention ---


@pytest.mark.parametrize("ref", REFERENCES)
def test_face_on_basis_is_proper_rotation_onto_z(ref):
    for z in _random_normals(500):
        R = fr.face_on_basis(z, reference=ref)
        np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)
        assert np.linalg.det(R) == pytest.approx(1.0, abs=1e-12)
        np.testing.assert_allclose(R @ z, EZ, atol=1e-12)


@pytest.mark.parametrize("ref", REFERENCES)
def test_face_on_x_is_projected_reference(ref):
    # The PA convention itself: x' is the reference projected into the disk plane
    ref = np.array(ref)
    for z in _random_normals(500):
        if abs(ref @ z) > 0.99:
            continue
        proj = ref - (ref @ z) * z
        np.testing.assert_allclose(
            fr.face_on_basis(z, reference=ref)[0], proj / np.linalg.norm(proj), atol=1e-12
        )


def test_face_on_basis_known_answers():
    np.testing.assert_allclose(fr.face_on_basis(EZ), np.eye(3), atol=1e-15)
    np.testing.assert_allclose(fr.face_on_basis(-EZ), np.diag([1.0, -1.0, -1.0]), atol=1e-15)


def test_face_on_basis_fallback_uses_least_aligned_axis():
    # reference parallel to zhat: x' must come from box y, the axis least aligned with zhat
    z = np.array([0.6, 0.1, 0.8])
    z /= np.linalg.norm(z)
    R = fr.face_on_basis(z, reference=z)
    ey = np.array([0.0, 1.0, 0.0])
    proj = ey - (ey @ z) * z
    np.testing.assert_allclose(R[0], proj / np.linalg.norm(proj), atol=1e-12)


def test_face_on_basis_equals_named_decomposition():
    # The exact rewrite the user wants: Rz(-alpha) Ry(-theta) Rz(-phi)  (maps.md, 2026-11-18)
    for ref in REFERENCES:
        ref = np.array(ref)
        for z in _random_normals(500):
            if abs(ref @ z) > 0.99:
                continue
            tilt = fr.rot_y(-np.arccos(z[2])) @ fr.rot_z(-np.arctan2(z[1], z[0]))
            r = tilt @ ref
            R = fr.rot_z(-np.arctan2(r[1], r[0])) @ tilt
            np.testing.assert_allclose(R, fr.face_on_basis(z, reference=ref), atol=1e-12)


# --- named matrices: active, right-handed ---


@pytest.mark.parametrize(
    ("rot", "v", "expected"),
    [
        (fr.rot_x, (0, 1, 0), (0, 0, 1)),
        (fr.rot_y, (0, 0, 1), (1, 0, 0)),
        (fr.rot_z, (1, 0, 0), (0, 1, 0)),
    ],
)
def test_rot_quarter_turn_is_right_handed(rot, v, expected):
    np.testing.assert_allclose(rot(np.pi / 2) @ np.array(v, float), expected, atol=1e-15)


@pytest.mark.parametrize("rot", [fr.rot_x, fr.rot_y, fr.rot_z])
def test_rot_inverse_is_negative_angle(rot):
    a = 0.7
    np.testing.assert_allclose(rot(-a) @ rot(a), np.eye(3), atol=1e-15)
    np.testing.assert_allclose(rot(a).T, rot(-a), atol=1e-15)


# --- Frame.rotated_z: the bar-alignment step ---

KW = {"purpose": "test", "pa_convention": "test"}


def _frame():
    z = np.array([0.3, -0.5, 0.8])
    return fr.Frame(
        center=np.array([1.0, -2.0, 3.0]),
        v_center=np.array([10.0, 0.0, -5.0]),
        rotation=fr.face_on_basis(z / np.linalg.norm(z)),
        tracers="disk",
        r_axis=10.0,
    )


def test_rotated_z_puts_direction_alpha_on_x():
    f = _frame()
    alpha = np.radians(130.0)
    # a point at azimuth alpha, height 0.4, in the original frame
    p_frame = np.array([2.0 * np.cos(alpha), 2.0 * np.sin(alpha), 0.4])
    p_box = f.center + f.rotation.T @ p_frame
    np.testing.assert_allclose(
        f.rotated_z(alpha, **KW).positions(p_box[None])[0], [2.0, 0.0, 0.4], atol=1e-12
    )


def test_rotated_z_keeps_centre_velocity_and_zaxis():
    f = _frame()
    g = f.rotated_z(1.1, **KW)
    np.testing.assert_array_equal(g.center, f.center)
    np.testing.assert_array_equal(g.v_center, f.v_center)
    np.testing.assert_allclose(g.rotation[2], f.rotation[2], atol=1e-15)
    assert g.r_axis == f.r_axis
    assert g.tracers == "disk"
    assert f.rotated_z(1.1, tracers="bar", **KW).tracers == "bar"


def test_rotated_z_pi_flips_sides_of_bar():
    # alpha + pi keeps the bar on x' and swaps y' > 0 / y' < 0 (the by-eye north flip)
    f = _frame()
    pts = RNG.normal(size=(100, 3)) + f.center
    a = f.rotated_z(0.4, **KW).positions(pts)
    b = f.rotated_z(0.4 + np.pi, **KW).positions(pts)
    np.testing.assert_allclose(b[:, :2], -a[:, :2], atol=1e-12)
    np.testing.assert_allclose(b[:, 2], a[:, 2], atol=1e-12)


def test_rotated_z_does_not_mutate_original():
    f = _frame()
    before = f.rotation.copy()
    f.rotated_z(0.9, **KW)
    np.testing.assert_array_equal(f.rotation, before)


# --- rot_steps: the per-rotation record that lands in product meta ---


def _disk(zhat, n=4000):
    # thin disk rotating about zhat, centred at c with bulk velocity v0
    zhat = np.asarray(zhat, float) / np.linalg.norm(zhat)
    e1 = np.cross(zhat, [1.0, 0.0, 0.0] if abs(zhat[0]) < 0.9 else [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(zhat, e1)
    r = RNG.uniform(0.5, 8.0, n)
    ph = RNG.uniform(0, 2 * np.pi, n)
    c, v0 = np.array([3.0, -1.0, 2.0]), np.array([50.0, 0.0, -20.0])
    pos = c + r[:, None] * (np.cos(ph)[:, None] * e1 + np.sin(ph)[:, None] * e2)
    vel = v0 + 200.0 * (-np.sin(ph)[:, None] * e1 + np.cos(ph)[:, None] * e2)
    return pos, vel


def test_face_on_steps_compose_to_face_on_basis_and_are_tilt_then_pa():
    for ref in REFERENCES:
        for z in _random_normals(200):
            steps = fr.face_on_steps(z, reference=ref)
            assert [s.axis for s in steps] == ["z", "y", "z"]
            np.testing.assert_allclose(
                fr.compose(steps), fr.face_on_basis_gram_schmidt(z, reference=ref), atol=1e-12
            )


def test_from_tracers_records_steps_and_convention():
    pos, vel = _disk((0.3, -0.5, 0.8))
    f = fr.Frame.from_tracers(pos, vel)
    assert f.pa_convention == "sim_x"
    assert len(f.rot_steps) == 3
    np.testing.assert_allclose(fr.compose(f.rot_steps), f.rotation, atol=1e-12)


def test_from_tracers_refuses_unnamed_non_default_reference():
    pos, vel = _disk((0.3, -0.5, 0.8))
    with pytest.raises(ValueError, match="pa_convention"):
        fr.Frame.from_tracers(pos, vel, reference=(0.0, 0.0, -1.0))
    f = fr.Frame.from_tracers(pos, vel, reference=(0.0, 0.0, -1.0), pa_convention="lon")
    assert f.pa_convention == "lon"


def test_rotated_z_appends_exactly_one_step():
    pos, vel = _disk((0.3, -0.5, 0.8))
    f = fr.Frame.from_tracers(pos, vel)
    g = f.rotated_z(0.6, purpose="bar onto x", pa_convention="bar_m2_arm_north")
    assert g.rot_steps[:3] == f.rot_steps
    assert g.rot_steps[3] == fr.RotStep("z", -np.degrees(0.6), "bar onto x")
    assert g.pa_convention == "bar_m2_arm_north"
    np.testing.assert_allclose(fr.compose(g.rot_steps), g.rotation, atol=1e-12)


def test_unrecorded_frame_stays_unrecorded():
    # A frame built from a bare matrix has no history; one appended step would not compose
    g = _frame().rotated_z(0.6, **KW)
    assert g.rot_steps == ()


def test_steps_that_disagree_with_rotation_are_refused():
    steps = fr.face_on_steps(np.array([0.3, -0.5, 0.8]))
    with pytest.raises(ValueError, match="rot_steps"):
        fr.Frame(np.zeros(3), np.zeros(3), np.eye(3), rot_steps=steps)


def test_to_dict_rot_steps_are_json_and_rebuild_rotation():
    import json

    pos, vel = _disk((0.3, -0.5, 0.8))
    f = fr.Frame.from_tracers(pos, vel).rotated_z(0.6, purpose="bar", pa_convention="bar")
    d = json.loads(json.dumps(f.to_dict()))
    rebuilt = fr.compose(fr.RotStep(**s) for s in d["rot_steps"])
    np.testing.assert_allclose(rebuilt, f.rotation, atol=1e-12)
    assert d["rot_steps"][-1]["purpose"] == "bar"
    assert d["pa_convention"] == "bar"


# --- B12 Model 2 LMC, snapshot_069 (newstars_lmc-069.h5 meta, regenerated 2026-11-19) ---

B12_LMC_069_ROTATION = np.array(
    [
        [-0.5935290311060807, 0.5772806150167279, -0.5607765872075843],
        [0.6972264630772352, 0.7168509323316868, 0.0],
        [0.4019932193695383, -0.39098827647526674, -0.827967160725481],
    ]
)


def test_b12_lmc_frame_reproduced_from_its_axis():
    z = B12_LMC_069_ROTATION[2]
    np.testing.assert_allclose(
        fr.face_on_basis(z, reference=(0.0, 0.0, -1.0)), B12_LMC_069_ROTATION, atol=1e-14
    )


def test_clouds_demo_reference_has_no_third_rotation():
    # ref = -z survives Rz(-phi) unchanged and Ry(-theta) keeps it in the x-z plane, so the PA step
    # is always 0: the clouds_demo frame IS the two-step (magclouds align_galaxy_xy) frame
    steps = fr.face_on_steps(B12_LMC_069_ROTATION[2], reference=(0.0, 0.0, -1.0))
    assert steps[2].angle_deg == pytest.approx(0.0, abs=1e-12)
    for z in _random_normals(200):
        if abs(z[2]) > 0.99:
            continue
        assert fr.face_on_steps(z, reference=(0.0, 0.0, -1.0))[2].angle_deg == pytest.approx(
            0.0, abs=1e-9
        )


def test_b12_lmc_pa_conventions_differ_by_130_41_deg():
    z = B12_LMC_069_ROTATION[2]
    x_simx = fr.face_on_basis(z)[0]
    x_lon = B12_LMC_069_ROTATION[0]
    signed = np.degrees(np.arctan2(np.cross(x_lon, x_simx) @ z, x_lon @ x_simx))
    assert signed == pytest.approx(130.4068, abs=1e-3)
