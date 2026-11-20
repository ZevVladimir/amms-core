---
paths:
  - "src/amms/core/analysis/maps.py"
  - "src/amms/core/analysis/frames.py"
  - "src/amms/core/plotting/maps.py"
  - "src/amms/core/products.py"
---

# Analysis/plotting layer (built 2026-09-04)

- `analysis/` and `plotting/` import **only numpy + matplotlib** — amms-core is
  installed into `~/.venvs/legacy-gadget` with `pip install -e <repo> --no-deps`.
  Snapshot loading stays in project-repo drivers (`io/` frozen). Pinned by
  `test_analysis_does_not_import_h5py`; h5py is lazy inside `products.py`. (2026-11-06:
  legacy-gadget has h5py via pygadgetreader, so laziness guards nothing today — kept as
  cheap insurance.)
- **`Map2D` is the compute/plot seam.** Batch script writes the product; notebooks and
  plot scripts load and render, never read snapshots. Carries `counts` beside `values`
  so shot noise stays visible; `meta` records the `Frame`. Pending: `save/load` still
  use `np.savez` — delegate to `products.write_product/read_product` (kind `sfrmap`).
- **`histogram2d` returns `[nx, ny]`, `imshow` wants `[ny, nx]`.** `project_map`
  transposes once, at construction. A transposed near-axisymmetric disk looks plausible
  (silent). Pin: one particle at `(5,0,0)`, `extent=10`, `bins=4` → `values[2, 3]`.
- **Face-on rotation = named steps (decided + built 2026-11-19):** `face_on_steps` →
  `RotStep`s Rz(-φ), Ry(-θ), Rz(-α) (φ = atan2(zy,zx), θ = arccos zz, α = in-plane angle
  of the tilted `reference`); `face_on_basis = compose(steps)`. Exact rewrite of the old
  Gram–Schmidt (kept as `face_on_basis_gram_schmidt`, cross-checked in `test_frames.py`
  with golden pins). `Frame` carries `rot_steps` (each with `purpose`, degrees) +
  `pa_convention`; `__post_init__` refuses steps that don't compose to `rotation`;
  frames built from a bare matrix have `rot_steps=()` and stay that way. `from_tracers`
  refuses a non-default `reference` without a named `pa_convention`.
- `reference` default is projected simulation x-axis (`sim_x`). Do not change it to `-z`:
  degenerates when the disk normal nears box z — how isolated AMMS ICs are built. B12
  passes `(0,0,-1)` = `line_of_nodes_clouds_demo` (`y'` = line of nodes).
- **ref = -z ⇒ α ≡ 0 for every zhat** (Rz leaves -z alone, Ry keeps it in x-z): the
  clouds_demo frame *is* the magclouds two-step `align_galaxy_xy` frame. The two-step
  form's flaw (x' jumps 90° near face-on vs box z) is why `sim_x` stays the default.
- Conventions differ by **130.41°** for the current B12 M2 LMC 069 frame (pinned). The
  older 130.65° was measured on an earlier frame (different centre/axis), not a bug.
- Bar split (Massana+2022 N/S comparison): `frame.rotated_z(alpha, purpose=,
  pa_convention="bar_m2_arm_north")`, α = φ₂ (`analysis/fourier.py`) + π·flip, flip by
  eye so the spiral arm is at y' > 0. Choice recorded in `b12.LMC_BAR_SPLIT`; chosen in
  the notebook on `diskstars_*` + `newstars_*` (same frame — assert meta equality).
- `fourier_phase` amplitude is |C_m|/C_0 (N-body particle convention) = **half** the A in
  Σ₀[1 + A cos m(φ−φ_m)]. Check the convention before comparing A₂ with a paper.
