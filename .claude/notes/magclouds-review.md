# magclouds review (2026-11-18) — deferred until ic-plots is implemented

`~/magclouds` = Himansh Rathore's utilities (github himanshrathore/magclouds, last commit
e578132 2026-02-13). Modules: `transform_galaxy.py` (COM, coords, rotations, alignment),
`disk_utils.py` (profiles, Fourier, bar), `halo_utils.py` (ρ, σ_r, β, M(<r)),
`halo_tools.py` (Hernquist/NFW, MakeGalaxy V200/CC), `snap_analysis.py`, `cosmology.py`.
All take (3, N) arrays (ours: (N, 3)).

## Rotations — DONE 2026-11-19 (see `.claude/rules/maps.md`)

Named steps built and pinned; convention kept exactly; `rot_steps` + `pa_convention` in
`Frame.to_dict()`. Fourier m=2 bar phase pulled forward into `analysis/fourier.py`.
Still open:
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
