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
- **Face-on rotation is Gram–Schmidt, not Euler angles**: `R @ zhat == [0,0,1]` by
  construction. `reference` fixes the PA; **default is projected simulation x-axis.**
  Do not change it to `-z`: `ref . zhat = -cos(theta)` degenerates when the disk normal
  nears box z — exactly how isolated AMMS ICs are built. The B12 driver passes
  `reference=(0,0,-1)` explicitly to match Rathore's `clouds_demo` frame (`y'` = line
  of nodes). The two conventions differ by **130.65 deg** for the LMC; the driver
  records `pa_convention` in `meta`.
