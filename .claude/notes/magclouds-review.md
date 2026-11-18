# magclouds review (2026-11-18) — deferred until ic-plots is implemented

`~/magclouds` = Himansh Rathore's utilities (github himanshrathore/magclouds, last commit
e578132 2026-02-13). Modules: `transform_galaxy.py` (COM, coords, rotations, alignment),
`disk_utils.py` (profiles, Fourier, bar), `halo_utils.py` (ρ, σ_r, β, M(<r)),
`halo_tools.py` (Hernquist/NFW, MakeGalaxy V200/CC), `snap_analysis.py`, `cosmology.py`.
All take (3, N) arrays (ours: (N, 3)).

## Rotations — user wants separate named matrices (reopens maps.md "not Euler" wording)

- Exact rewrite available: `face_on_basis` == Rz(ψ)·Ry(-θ)·Rz(-φ), φ = atan2(zy, zx),
  θ = arccos zz, ψ = -atan2(r_y, r_x) with r = Ry(-θ)Rz(-φ)·reference. Max diff 6e-15
  over 10k random normals × both references, outside the |ref·zhat| > 0.99 fallback
  (decomposed form needs the same fallback). → no product changes, B12 130.65° intact.
- magclouds `alignGal.align_galaxy_xy` = steps 1-2 only (no ψ): near face-on x' jumps 90°
  (zhat tilted 1e-3 toward x vs y); ours 0.06°. Step 3 is what keeps isolated-IC time
  series oriented.
- `frames.py` has **no tests** — rewrite must pin today's matrices first.
- Open questions asked, unanswered:
  1. Keep convention exactly, just three named matrices? (recommended) vs magclouds 2-step.
  2. Record φ/θ/ψ (deg) in `Frame.to_dict()` → new fields in every Map2D meta (schema).
  3. Port scope (below).
  4. Has the user used magclouds β/σ_r in results? (affected by bug 1). Tell Himansh? user's call.

## Silent bugs found (verified numerically)

1. `transform_galaxy.py:211,246` `phi = np.arctan(y/x)` ∈ (-π/2, π/2) → spherical
   velocities sign-flipped for x<0: radial orbits give β = 0.82 (true 1), v_r off by up to
   7.8 on O(1) speeds; solid rotation gives v_φ<0 for 50%. Hits `get_halo_veldisp_profile`,
   `get_halo_anisotropy_profile`. Cylindrical *velocities* unaffected (no φ).
2. `disk_utils.py:661` unbinned Fourier phase `/2` for every m (binned uses `/m`); arctan φ
   is fine for even m only → m=1 lopsidedness wrong, m=2 bar fine.
3. `get_disk_vphi_profile` / `get_disk_vrad_profile` ignore `mass` (unweighted) — wrong for
   gridded-IC gas (background cells).
Loud: `HernquistHalo.velocityDispersion` calls undefined `self.rs()`;
`get_omega_bar_window` IndexError when len(times) % window == 0.

## Port list (reimplement: numpy, (N,3), mass-weighted, arctan2)

- Now-ish (IC plots v2): spherical velocities + σ_r/σ_θ/σ_φ + β(r) → halo panel (MakeGalaxy
  halo isotropic unless AniR); σ_R/σ_φ/σ_z; ρ(z) in an annulus (theirs: one x,y box).
- Later: iterative velocity shrinking sphere (`get_iterative_velocity_COM`) → frames.py for
  stripped/interacting systems; ring j(R) (warps); Fourier A_m(R), bar length (Lucey+23,
  Athanassoula & Misiriotis 02), pattern speed (LMC bar); van der Marel & Cioni 01 (ρ, φ)
  and gnomonic tangent plane → sky.py.
- IC-gen package: `NFWtoHern` (van der Marel 2012 A11/A12), `MakeGalaxyParamsHern`.
- Skip: `snap_analysis` readers (io/ frozen), `cosmology.py` (non-cosmological), `get_snaps`.
