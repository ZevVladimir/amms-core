# Config.sh / param.txt for SH03 and SMUGGLE runs

Read before proposing Config.sh flags or param.txt values. Template for new runs:
`smc_001_edw1_sh03`'s Config.sh / param.txt / env.sh (see `.claude/rules/arepo-output.md`).

## Decision: plain hydro + gravity + SH03 SFR first, SMUGGLE after

Validates param.txt/units/mesh independently of SMUGGLE calibration. Done for `edw1`;
`smct1` needs IC fixes first (see `.claude/rules/ics.md`).

Dry-run flag set (derived from `Template-Config.sh` + docs + IC header):

    NTYPES=6  VORONOI  HAVE_HDF5  DOUBLEPRECISION=1  SELFGRAVITY
    GRAVITY_NOT_PERIODIC  HIERARCHICAL_GRAVITY  REGULARIZE_MESH_CM_DRIFT
    REGULARIZE_MESH_FACE_ANGLE  COOLING  USE_SFR  SOFTEREQS  METALS
    STELLARAGE  NSOFTTYPES=4   (+ OVERRIDE_PEANOGRID_WARNING, needed in practice)

Riemann solver/reconstruction left at defaults. Undecided:
`REFINEMENT_SPLIT_CELLS`/`MERGE_CELLS`, `ADAPTIVE_HYDRO_SOFTENING`, per-type softening
(generator used flat 0.1 kpc).

## Don't copy from `examples/galaxy_merger_star_formation_3d`

~1e6 Msun cells in kpc/h. Under `REFINEMENT_VOLUME_LIMIT`, Volume < 2·`MinVolume`
returns "don't refine" *before* the mass criterion
(`arepo-smuggle:src/refinement/criterion_refinement.cc:133` vs `:266`), so its
`MinVolume 1` silently disables mass refinement for ~600 Msun cells. Same for
`MinimumComovingHydroSoftening 1.0`. Its `HubbleParam 0.6774` is wrong for h=1 ICs.

## SMUGGLE (source-verified; the doc stub is useless)

- Plugin module; authoritative param list is `onRegisterParameters` in
  `arepo-smuggle:src/modules/smuggle/module_smuggle.cc:42-91`, not `parameters.cc`.
- **`SMUGGLE_SFR` requires `USE_SFR`** (`arepo-smuggle:src/modules/smuggle/smuggle_sfr.cc:25`).
  SH03 params (`MaxSfrTimescale`, `FactorSN`, `FactorEVP`, `TempSupernova`,
  `TempClouds`, `FactorForSofterEQS`) live in `parameters.cc`'s `#if !defined(SMUGGLE_SFR)`
  branch (~1962) and **do not apply** under SMUGGLE.
- `SMUGGLE_RADIATION_FEEDBACK` needs `SMUGGLE_STAR_FEEDBACK` + `GFM_STELLAR_EVOLUTION`
  (`arepo-smuggle:src/io/parameters.cc:3386`); `onCheckModuleDependencies` is a no-op
  (`module_smuggle.cc:40`), so thermal-only `SMUGGLE_STAR_FEEDBACK` doesn't need GFM.
- `METALS` requires `USE_SFR`.
- **Minimal set:** `SMUGGLE USE_SFR SMUGGLE_SFR SMUGGLE_STAR_FEEDBACK` + dry-run flags.

## Open blocker — physical, not mechanical

8 params registered with **no default** (`module_smuggle.cc:53-67`), deliberately (optional
ones use `add_param_*_with_default`): `CritOverDensity`, `DensThreshold`,
`SfrEfficiency`, `FeedbackEfficiency`, `ThermalFeedbackEfficiency`,
`FeedbackWeightingPow1`, `FeedbackWeightingPow2`, `FeedbackWeightingType`.
**Do not invent values** — wrong calibration fails silently as wrong physics. Source:
Marinacci+2019 (arXiv:1905.08806) or Federico Marinacci.
`FeedbackWeightingType` switch (`arepo-smuggle:src/modules/smuggle/stellar_feedback_util.cc:319-364`):
0 top-hat/volume, 1 top-hat/mass, 2 kernel volume, 3 kernel mass, 4 omega, 5
density+distance (Pow1, Pow2), 6 omega inverse-density (Pow1), 7 as 6 with pivot at
`10*DensThreshold` (Pow1). Pow1/Pow2 are dead unless type is 5/6/7.
