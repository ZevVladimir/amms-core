# amms-core

**AMMS = Arepo Milky-way Magellanic-clouds Simulations.**

**These are HYDRO runs with AREPO + SMUGGLE, and they are NON-COSMOLOGICAL.**
Isolated and interacting galaxy models, so `ComovingIntegrationOn = 0`:
`TimeBegin`/`TimeMax` are physical times in code units, **not** scale factors, and
`z_start`, `z_end`, `sigma_8`, `n_s`, `omega_*` are dead fields. Do not design
around cosmological boxes — that error was already made once and caught.

What actually discriminates runs: which galaxies are present, their masses and gas
fractions, particle/cell mass resolution, softening, and the `SMUGGLE_*` block in
`Config.sh` (which for SMUGGLE genuinely *is* the physics).

Planned ladder: SMC alone → LMC alone → SMC+LMC → MW+SMC+LMC (production).

**The ICs are the weakest provenance link, and they are upstream of this user.**
They come from another grad student's N-body runs, are actively being revised, will
be shared across many runs, and are not in any git history this user controls. In
practice IC revision *n* and *n+1* will share a filename. **Hash the IC file at
time of use** (sha256, or size + head/tail digest if huge) — that information is
destroyed the moment the file is overwritten, so it cannot be backfilled.

AREPO/SMUGGLE may be built by someone else, so `code.commit` is a property of a
build this user does not own. Copy `Config.sh` and compiler output *into* the run
directory rather than pointing at a source tree that may be rebuilt underneath.
This makes snapshot-embedded `/Config` more valuable, not less.

Baseline comparison targets exist: the professor's older, less accurate runs.
Eventually worth registering as read-only comparison entries. Not now.

Matching the group's existing directory conventions is explicitly **not** a goal;
the user wants consistency and understandability for themselves.

Shared core package pinned by every AMMS project repo. AREPO simulations, UA HPC,
Slurm. A breaking change here silently invalidates old analyses, so treat the
public API as load-bearing and version deliberately.

Working style: `~/.claude/CLAUDE.md`. The user keeps their own decision log and
relies on it primarily; this file is mine, and exists so I stop re-deriving or
relitigating settled calls.

## BUILD FREEZE (set 2026-08-27) — read before proposing any new module

As of this date the user has **no AREPO runs on disk**, **no estimate of run
count**, and **no settled job pattern**. Anything whose design depends on those
unknowns is speculation and is frozen:

- `metadata.py` — schema field names were invented, never checked against a real
  `param.txt`.
- `codes/arepo.py` — the parameter-name mapping is a guess about this AREPO build.
- `io/` — there are no snapshots to read.
- `registry/`, `cli.py`, dashboard, cookiecutter, Obsidian vault.
- `events.jsonl` folding — designed for 100-task arrays, which may never happen.
  `_yamlio.py` already implements the primitives; leave them, build nothing on them.

**Do not resume these just because the Build Order section lists them next.**
Resume only once a real run exists and its `param.txt`, `Config.sh`, directory
listing, and snapshot header have actually been seen. The hand-written
`metadata.yaml` for run #1 is the specification for the schema — discovered, not
designed.

Still worth building, since their value does not depend on the unknowns:
`config/{machines.yaml,paths.py}` (cluster paths are facts about Puma, and run #1
must be placed *somewhere*), `plotting/provenance.py` (figure stamping needs zero
AREPO knowledge), and the `/xdisk` expiry check in `hpc/storage.py` (the
allocation is deleted, not archived).

**The critical path is not this repo.** It is getting AREPO compiled and run #1
launched on Puma. Prefer helping with that over extending this package.

**Freeze status as of 2026-09-01:** AREPO now builds and runs on Puma, but only a
shipped 1D test problem (`examples/shocktube/shocktube_sod_1d`). That is enough to
retire the *snapshot-format* questions below, and not enough to unfreeze
`metadata.py` — no science run, no ICs, no SMUGGLE config, still no job pattern.

## AREPO on Puma — established 2026-09-01, first successful build and run

- **Source:** `git@bitbucket.org:volkerspringel/arepo.git`, branch
  `Arepo2-smuggle-mod` (`d323be6`, Federico Marinacci, 2026-07-20). Private repo,
  access granted; SSH key auth, port 22 open from compute nodes. 17 SMUGGLE
  branches exist — `lucchini_smuggle` is Magellanic-relevant and was *not* chosen;
  `Arepo2-smuggle-mod` is the active development line. Clone at
  `/home/u2/zvladimir/codes/arepo-smuggle` on Puma, read-only copy at
  `~/codes/arepo-smuggle` on the laptop.
- **`git clone --recurse-submodules` is mandatory.** `lib/safeintegral` is a header
  library the source includes. Without it every compile fails on a missing header,
  and because `make` was running with `-i` the failures printed as
  `Error 127 (ignored)` and the build proceeded to link with zero object files —
  presenting as a linker problem, not a source problem.
- **AREPO2 is C++**: 482 `.cc` files vs 27 `.c`, `src/main/main.cc`. A systype must
  set **both `CC` and `CPPC`** to `mpicxx -std=c++11`, and must *not* put `-std=c11`
  in `OPTIMIZE`. An unset `CPPC` makes the recipe exec `-std=c11` as a program.
- **`SYSTYPE="Puma"` existed in `buildsystem/systypes.make` but was dead**: it
  hardcoded Puma's 2020 stack (`openmpi3-gnu8/3.1.4`, `gsl/2.6`, `hdf5/1.10.5`,
  `hwloc/2.2.0`) — all four directories deleted by an OS refresh — and set neither
  `CC` nor `CPPC`. Fixed on local branch `puma-buildsystem`; worth upstreaming.
- **Current Puma stack:** default-loaded `gnu13/13.2.0`, `openmpi5/5.0.5`,
  `hwloc/2.13.0`, `ucx`, `libfabric`. Under `gnu13`: `gsl/2.7.1`, `hdf5/1.14.0`
  (serial). Under `gnu13-openmpi5`: `fftw/3.3.10`, `phdf5/1.14.0`. Build module set:
  `gnu13 openmpi5 gsl hdf5 fftw`.
- **Reference module-exported `*_DIR` vars, never literal paths** — that is exactly
  what rotted. Two names are unusable in a systype block: **`FFTW_LIB` and
  `HWLOC_LIB` are assigned in `Makefile` before `systypes.make` is included**, so
  the module's env values are shadowed and `-L$(HWLOC_LIB)` yields `-L-lhwloc`.
  Use `*_DIR` or `*_INC`.
- **`GMPLIB := -lgmp` is unconditional** in the link line; `libgmp.so` must be
  present. FFTW is linked only under `PMGRID`/`TURB_POWERSPEC`, HWLOC only under
  `IMPOSE_PINNING` — so neither matters for non-cosmological runs.
- **Avoid `-march=native`** even though other systypes use it. Puma has more than
  one node generation; a binary built on one and run on another dies with
  `Illegal instruction`, which reads like a code bug.
- **Build one binary per run directory:** `make TARGET_DIR=<dir>` reads
  `<dir>/Config.sh` and writes `<dir>/Arepo` plus `<dir>/build/`. This is upstream's
  own mechanism and it *is* the "copy Config.sh and compiler output into the run
  directory" decision — wrap it in `codes/arepo.py`, do not reimplement it.
  `Makefile.systype`, `/Config*.sh` and `/run` are already gitignored upstream.
- **Test framework:** `./test.py --no-cleanup <path/relative/to/examples>` (root
  `test.py` is a symlink to `examples/test.py`; names are paths, so
  `shocktube/shocktube_sod_1d`, not `shocktube_sod_1d`). It copies the example,
  runs `create.py`, builds, runs `mpiexec -n N ./Arepo param.txt`, then `check.py`.
  Output goes to `<repo>/run/examples/<name>/` — symlink `run` onto `/xdisk`.
  Needs numpy, scipy, h5py, matplotlib (+pyyaml); lives in `~/.venvs/arepo-tests`,
  deliberately **not** `~/.venvs/amms`. `documentation/code_tests.md` refers to a
  `test.sh` that does not exist on this branch.
- **Docs worth reading before guessing:** `documentation/getting_started.md`,
  `code_tests.md`, `core_param_options.md`, `core_unit_system.md`,
  `modules_smuggle_sfr.md`. No SMUGGLE *example* ships, so validating SMUGGLE
  physics needs a setup built from that doc, not a shipped test.

## Snapshot and output layout — observed, no longer guessed

- **`/Config` and `/Parameters` HDF5 groups ARE embedded in snapshots.** Confirmed
  2026-09-01 on `Arepo2-smuggle-mod`. These are the authoritative provenance
  source; `param.txt` is the fallback. This retires the old open question.
- **The resolved parameter dump is `<paramfile>-usedvalues`** (e.g.
  `param.txt-usedvalues`), written to the **run directory root**, not `OutputDir`.
  It contains AREPO's own defaults for anything the user omitted.
- **The parameter set is a function of `Config.sh`** — AREPO reads only the
  parameters its compiled options need (62 for the 1D sod test; a SMUGGLE run will
  have far more). **Therefore `metadata.py` must not enumerate AREPO parameters.**
  Let `/Parameters` and `*-usedvalues` carry parameter truth; keep `metadata.yaml`
  for scientific intent (which galaxies, masses, gas fractions, resolution) that
  AREPO has no concept of.
- **`output/end` is an empty file written on clean termination.** Use it as the
  completion sentinel in `registry/scan.py` — far more reliable than parsing logs.
- Run-dir contents: `Arepo`, `build/`, `Config.sh`, `param.txt`,
  `param.txt-usedvalues`, `ics.hdf5`, `uses-machines.txt`, `output/`.
- `output/` contents: `snap_NNN.hdf5`, `restartfiles/`, `end`, and the logs
  `balance.txt cpu.txt domain.txt energy.txt hostmemory.txt info.txt memory.txt
  timebins.txt timings.txt`. Note `cpu.txt` was 4.4 MB for a 100-cell 1D test,
  but that test sets `DEBUG` and `TimeBetStatistics 0.01`, so treat it as an upper
  bound on verbosity rather than a size estimate for production runs.
- Non-cosmological reading confirmed from the code's own output:
  `ComovingIntegrationOn 0`, and `Omega0`/`OmegaLambda`/`OmegaBaryon`/`HubbleParam`
  all 0.

## Analysis + plotting layer — built 2026-09-04, first real science output

**The module build order was deliberately reordered.** `analysis/{frames,maps,sfr}.py`
and `plotting/maps.py` were built *before* `io/`, because they take plain `(N, 3)` numpy
arrays and need zero snapshot knowledge — the freeze reason for `io/` does not reach
them. Snapshot loading stays in the **project repo's** driver
(`~/lmcsmcmw/scripts/sfr_maps_b12.py`), which is why `amms-core` is installed into
`~/.venvs/legacy-gadget` with `pip install -e <repo> --no-deps`. That works only while
`analysis/` and `plotting/` import nothing but numpy and matplotlib. Keep it that way.

- **`Map2D` is the compute/plot seam.** Batch script writes npz under
  `$AMMS_PRODUCTS/<dataset>/`; notebooks and plot scripts load and render, never read
  snapshots. It carries `counts` beside `values` so shot noise stays visible, and
  `meta` records the `Frame` so a cached product is self-describing.
- **`histogram2d` returns `[nx, ny]`, `imshow` wants `[ny, nx]`.** `project_map`
  transposes once, at construction. A transposed map of a near-axisymmetric disk looks
  entirely plausible, so this is a silent failure — the regression pin is a single
  particle at `(5,0,0)`, `extent=10`, `bins=4`, landing at `values[2, 3]`.
- **Face-on rotation is Gram–Schmidt, not Euler angles.** `R @ zhat == [0,0,1]` then
  holds by construction, with no quadrant cases. `reference` fixes the position angle
  and the **default is the projected simulation x-axis**. Do not change that default to
  `-z`: `ref . zhat = -cos(theta)`, so `-z` degenerates when the disk normal nears the
  box z-axis — exactly how the isolated AMMS ICs are built. The B12 driver passes
  `reference=(0,0,-1)` *explicitly* to match Rathore's `clouds_demo` frame (the
  spherical basis, `y'` = line of nodes) for figure-by-figure comparison. The two
  conventions differ by **130.65 deg** for the LMC, so figures are not
  cross-comparable; the driver records `pa_convention` in `meta`.
- **`shrinking_sphere_center(tol=0.01)` stops prematurely on tidally extended tracers.**
  LMC disk stars span 48.8 kpc from the COM, and shaving thin outer shells moves the
  center by under 10 pc, so `patience=2` is satisfied while the radius is still tens of
  kpc. `tol=1e-4` *or* `r_init=10` converges to 0.088 kpc of Rathore's independent
  center; `shrink` (0.9 vs 0.7) is irrelevant. The function returns only the center —
  adding `(final_radius, n_iter)` would have made this a five-second diagnosis instead
  of a parameter sweep.

### B12 Model 2 — observed 2026-09-04, no longer guessed

`/xdisk/gbesla/group/b12/lmc_smc_mw/model2/snaps/snapshot_069` confirmed readable (the
`clouds_demo` notebook's `/xdisk/gbesla/himansh/...` path is irrelevant and unreadable).
IC ID blocks, decoded from per-type min/max — every boundary exact:

    LMC  gas 1-300,000            dm 300,001-400,000      disk 400,001-1,400,000
    SMC  gas 1,400,001-1,700,000  dm 1,700,001-1,714,000  disk 1,714,001-1,814,000

Blocks sum exactly to `N_LMC_INIT` and `N_SMC_INIT`. SMC dm is **14,000**, confirming the
B12 Table 1 misprint. **Max ID anywhere is 1,814,000, so B12 Model 2 has NO live MW
particles** — the MW is an analytic potential. Consequences: `galaxy_mask` is validated
(0 unassigned of 468,486 star particles), and a perturber-direction `reference` cannot
come from this snapshot; it would have to come from the paper's orbit parameters.

- **Gas particles carry the high flag bit too**, not only stars. Never restrict the
  parent-ID decode to `ptype == "star"`.
- **Star IDs are not unique** and collide with live gas IDs — 468,486 stars over a
  600,000-ID gas space. Fine for range-based `galaxy_mask`; **do not track a star across
  snapshots by ID.** The flag bit is orthogonal to formation time.
- All star particles share one mass, 1831.48 Msun.
- **315,969 of 335,102 LMC stars have formation time exactly 0** — ~95% of all
  new-star mass, in a single SFH bin. Almost certainly a clock reset from a prior
  relaxation run. **Exclude from any SFH or mean-SFR**; an `age < 0.1` cut is unaffected.
  Asked Rathore, unanswered as of 2026-09-04.
- Present day: 2,664 LMC stars younger than 100 Myr, Sigma_SFR integrating to
  **0.0488 Msun/yr** (observed LMC is ~0.2). Independently cross-validated — the 1-D
  `sfh()` first four bins average 0.0486. Keep that agreement as a regression pin; it
  simultaneously checks the `h` factors, the `dt * 1e9`, `pixel_area`, and the transpose.
- The SFH is flat at ~0.036 Msun/yr across the run once the `ft == 0` spike is removed.
  There is no decline and no pericenter starburst in this window — do not go looking for
  a physical explanation of a trend that is an artifact of including that bin.

## smc_test — SMUGGLE Config.sh/param.txt investigation (started 2026-09-21, in progress)

First real IC for the ladder's first rung landed at
`/groups/gbesla/zvladimir/ics/smc_test/ics_smc.hdf5`, generated by a
Hernquist-halo + exponential-disk tool (`MakeGalaxy_puma9_modified_bulge`;
`zev_smcic_params.txt`/`ics_smc.hdf5.parameters` are the *generator's* input,
not AREPO's). **sha256 recorded 2026-09-21:**
`ba288d154e51774b106e296d44504eae7da263b6e84339cf5fdd4ab701930a6b`.

- Header (`h5py`, no `h5dump` in `legacy-gadget`): `BoxSize=0.0`
  (non-periodic/vacuum), `NumPart_Total=[522000 gas, 500000 halo/dm, 1044000
  disk stars, 0, 0, 1 BH seed]`, `HubbleParam=1.0`, no bulge. PartType0 and
  PartType2 both carry `Metallicity`; PartType2 also carries
  `StellarFormationTime` (pre-set ages from the generator's
  `DiskPopMode=exponential`). `Flag_DoublePrecision=0` — IC is float32, so
  `Config.sh` must NOT set `INPUT_IN_DOUBLEPRECISION`.
- Units confirmed by mass-budget cross-check (halo `MassTable[1]*N[1]` ≈
  1.796 vs `M200=1.84741` in the generator params — consistent once
  disk+gas+BH are subtracted): standard GADGET/AREPO default —
  `UnitLength_in_cm=3.085678e21` (kpc), `UnitMass_in_g=1.989e43` (1e10 Msun),
  `UnitVelocity_in_cm_per_s=1e5` (km/s). Inferred from internal consistency,
  not yet confirmed against an explicit unit note from the generator itself.
- `documentation/modules_smuggle_sfr.md` is a stub ("please do not use this
  module", no param list) — ground truth came from reading
  `src/modules/smuggle/module_smuggle.{h,cc}` and `src/io/parameters.cc`
  directly, not from docs. Confirms the "don't guess AREPO param names"
  freeze reasoning was right to be paranoid about.

**Decision: build and run a plain (non-SMUGGLE) hydro+gravity+SH03-SFR dry
run first**, to validate param.txt/units/mesh mechanics independently of
SMUGGLE calibration, before spending time on SMUGGLE physics.
**Decision: run directory is `arepo-smuggle/run/smc_test/sh03`** (mirrors
the shocktube test's `run/` convention, symlinked onto `/xdisk` on Puma) —
chosen over nesting it under the `smc` project repo, since `codes/arepo.py`
(which would own that convention) is still frozen. Slug is `sh03`, named for
the SFR model this run validates (Springel & Hernquist 2003), not the
"dry run" framing — leaves room for a `smuggle`-flagged sibling run later
in the same `smc_test/` directory without renaming this one.

Dry-run `Config.sh` candidate (derived from `Template-Config.sh` comments +
`core_param_options.md` + the IC header, not yet built/tested):

    NTYPES=6  VORONOI  HAVE_HDF5  DOUBLEPRECISION=1  SELFGRAVITY
    GRAVITY_NOT_PERIODIC  HIERARCHICAL_GRAVITY  REGULARIZE_MESH_CM_DRIFT
    REGULARIZE_MESH_FACE_ANGLE  COOLING  USE_SFR  SOFTEREQS  METALS
    STELLARAGE  NSOFTTYPES=4

  Riemann solver and reconstruction sections deliberately left at AREPO's
  defaults (no flags set) rather than picking one — no reason yet to deviate.
  Still undecided: `REFINEMENT_SPLIT_CELLS`/`REFINEMENT_MERGE_CELLS` (doc
  calls this "generally true" for real runs but not required for a smoke
  test), `ADAPTIVE_HYDRO_SOFTENING`, and per-type softening lengths (the
  generator used a flat 0.1 kpc for its own equilibrium calc — a reasonable
  start, not necessarily right for the sim's mean interparticle spacing).

**SMUGGLE findings (source-verified, file:line cited on
`/home/u2/zvladimir/codes/arepo-smuggle`):**
- SMUGGLE is a plugin module (`BaseModule`/`ModuleManager`), not wired
  through the legacy `parameters.cc` tag list. `onRegisterParameters` in
  `src/modules/smuggle/module_smuggle.cc:42-91` is the authoritative param
  list — not the doc stub, and not `parameters.cc`.
- **`SMUGGLE_SFR` requires `USE_SFR`** (`smuggle_sfr.cc:25`) — layered on
  top of, not exclusive with, the base SFR switch. The classic SH03 params
  already sitting in `zev_smcic_params.txt` (`MaxSfrTimescale`, `FactorSN`,
  `FactorEVP`, `TempSupernova`, `TempClouds`, `FactorForSofterEQS`) are
  registered only in `parameters.cc`'s `#if !defined(SMUGGLE_SFR)` branch
  (~line 1962) and **do not apply once `SMUGGLE_SFR` is on** — different
  parameterization entirely (density-threshold-based, not timescale-based).
- `SMUGGLE_RADIATION_FEEDBACK` requires both `SMUGGLE_STAR_FEEDBACK` and
  `GFM_STELLAR_EVOLUTION` (`parameters.cc:3386`), but
  `ModuleSmuggle::onCheckModuleDependencies` is a no-op
  (`module_smuggle.cc:40`) — so **minimal `SMUGGLE_STAR_FEEDBACK` (thermal
  injection only, no radiation feedback) does not require
  `GFM_STELLAR_EVOLUTION`.**
- `METALS` requires `USE_SFR` (`parameters.cc`, cross-module `#error` block
  ~line 3350s) — already satisfied by the dry-run flags above.
- **Minimal SMUGGLE flag set:** `SMUGGLE  USE_SFR  SMUGGLE_SFR
  SMUGGLE_STAR_FEEDBACK` (+ the dry run's mesh/gravity/precision flags, +
  `METALS`/`STELLARAGE` already required by the IC's fields).

**Open blocker — physical, not mechanical.** `onRegisterParameters`
(`module_smuggle.cc:53-67`) registers 8 SMUGGLE parameters via plain
`add_param_double`/`add_param_int` with **no default** — `param.txt` must
supply real values or the run refuses to start: `CritOverDensity`,
`DensThreshold`, `SfrEfficiency` (SFR); `FeedbackEfficiency`,
`ThermalFeedbackEfficiency`, `FeedbackWeightingPow1`, `FeedbackWeightingPow2`,
`FeedbackWeightingType` (feedback). None exist in any file seen so far.
**Do not invent values** — unlike a missing/misspelled flag (fails loudly),
a plausible-but-wrong calibration number here fails silently as wrong
physics. Source candidates: Marinacci et al. 2019 (arXiv:1905.08806, cited
in the doc stub) or Federico Marinacci directly. **`FeedbackWeightingType`'s
switch has now been read** (`stellar_feedback_util.cc:319-364`) — it selects
the feedback-kernel weighting, not the calibration constants: `0` top-hat/volume,
`1` top-hat/mass, `2` kernel-weighted volume, `3` kernel-weighted mass, `4`
omega-weighted, `5` density+distance-weighted (uses `FeedbackWeightingPow1/2`),
`6` omega-weighted with inverse density bias (uses `Pow1`), `7` omega-weighted
inverse density bias with a pivot at `10*DensThreshold` (uses `Pow1`). Reading
the switch narrows *which other params matter* (`Pow1`/`Pow2` are dead unless
type is 5/6/7) but still does not supply a value for `FeedbackWeightingType`
itself or the two `Pow` constants — that's paper/Federico territory, same as
the other 7. Confirmed separately: every one of the 8 params uses
`add_param_double`/`add_param_int` (no default arg), while genuinely optional
SMUGGLE params elsewhere in the same function (`MinMassFracForStellarEvolution`,
`MaxStromRadFac`) use `add_param_double_with_default` — so the missing defaults
are a deliberate "you must supply this" design, not an oversight to route around.

**Next steps:**
1. Finish the dry-run `param.txt` (needs `TimeBegin`/`TimeMax` for a short
   smoke test, per-type softenings, output cadence) and settle the three
   undecided `Config.sh` flags above.
2. Build: `make TARGET_DIR=arepo-smuggle/run/smc_test/sh03`, then a short
   interactive `mpiexec -n N ./Arepo param.txt` smoke test before `sbatch`.
3. In parallel: source the 8 SMUGGLE calibration values (paper or Federico).
   `FeedbackWeightingType`'s switch has been read (see above) — it narrows
   which other params are live but does not supply values.

## Settled — argue only with new evidence, and name the decision if you do

- **AREPO** is the only simulation code. GADGET-style HDF5 snapshots.
- **Slurm on UA HPC. The clusters are Puma and Lynx (new).** Ocelote and El Gato
  are **decommissioned** — do not propose them, and do not add them to
  `machines.yaml` or `detect_machine`. Tiers: `/home`, `/groups`, `/xdisk` (time-limited
  allocation — expires and is *deleted*), `/rental` (long-term, must not compute
  from it), `/tmp` (node-local, cleared at job end). Site guidance: stage to
  `/tmp` for repeated reads, keep files-per-directory in the hundreds not tens of
  thousands, avoid tight open/close loops.
- **PI/group is `gbesla`** (confirmed 2026-08-31). Home is `/home/u2/zvladimir`;
  HPC username is `zvladimir`. `/xdisk/gbesla/zvladimir/` exists and is the user's
  own space. `/xdisk/gbesla/group/` is the **shared group data area** — this is
  where read-only comparison data lives, including the professor's older runs
  (e.g. Besla+2012 at `/xdisk/gbesla/group/b12/lmc_smc_mw/model2/snaps/`). Other
  members' `/xdisk/gbesla/<netid>/` dirs are **not** group-readable; never assume
  a path under someone else's name can be read.
- **Site python module + venv. Never conda/mamba.** Consequence:
  `environment.yml` cannot describe this environment, so reproducibility rests on
  `env/modules.txt` + committed `env/locks/`.
- **`amms` namespace package**; this repo owns `amms.core`. Never create
  `src/amms/__init__.py` — its absence is what allows a future `amms-viz`.
- **pydantic v2 with `extra="forbid"` on every model.** Forbid is the point:
  `phyics: hydro` would otherwise parse cleanly and leave `physics` as None.
- **Four projects, one per galaxy configuration**, each its own repo pinning this
  package: `smc`, `lmc`, `lmcsmc`, `mwlmcsmc`. Four independent run counters. The
  user chose this over a single project with a `system:` metadata field; do not
  reopen it. Cross-ladder chronology is recoverable from `created` dates, and the
  shared-analysis-code cost is what `amms-core` itself absorbs.
- **Hash the ICs at time of use** and copy `Config.sh` + compiler output into the
  run directory. Record IC filename, size, sha256 (head/tail digest if huge), date
  obtained, and who produced it. Build this utility the moment real ICs land —
  before running anything with them — because the information cannot be backfilled.
- **SIM_ID is `<project>_<NNN>_<slug>`** (`mwsat_007_fiducial`). Underscore
  separates the three fields, hyphens only inside the slug. `parse()` enforces a
  round-trip so exactly one spelling exists per identity. **No physics prefix** —
  it duplicates `physics:` and becomes a lie after an nbody→hydro restart, by
  which point it is baked into published figure filenames.
- **h5py is the default IO backend**; pygadgetreader is a registered alternate
  for legacy binary snapshots and cross-checks. pygadgetreader is unmaintained —
  a numpy bump would otherwise break every analysis script simultaneously.
- **Cached products live in a parallel tree `$WORK/products/<sim_id>/`**, not
  inside the run directory. Keeps small derived data separately syncable.
- **`requires-python = ">=3.10"`.** Puma offers `python/3.11/3.11.4` (the `(D)`
  default) **and** `python/3.14/3.14.2`; `env/modules.txt` pins 3.11.4. Avoid
  3.11-only syntax so the floor stays honest. The floor rests on the lock-file
  argument, not on what modules exist — 3.14 being available does not reopen it.
- **Committed lock per (cluster, python) pair**, `env/locks/<cluster>-py<ver>.txt`.
  One shared requirements.txt across clusters is a lie discovered when a paper
  figure won't regenerate.

## Invariants — violating these is a bug, not a style preference

1. **`ids.py` and `metadata.py` import nothing else from this package.** The
   SIM_ID string also lives in directory names, figure filenames and Obsidian
   titles, where it cannot be refactored, so its code must be the most stable here.
2. **There is no `save_metadata()` and there must never be one.**
   `metadata.yaml` is human-curated and `yaml.dump` has no concept of comments, so
   any programmatic rewrite deletes them all. `amms` reads that file and writes
   only `state.yaml` (machine-owned) and `events.jsonl` (append-only).
   `init_run()` writes the stub once and refuses to overwrite. **Enforcement is
   the absence of the function** — do not add a convenience wrapper.
3. **Jobs never read-modify-write shared state.** A 100-task Slurm array loses 99
   updates and can destroy the file. Jobs append one short line to `events.jsonl`
   via a single `os.write` on an `O_APPEND` descriptor; `amms scan` folds events
   into `state.yaml` from one process.
4. **No hardcoded cluster paths.** Everything resolves through
   `amms.core.config.paths`. A diff containing `/xdisk` or `/groups` outside
   `machines.yaml` is wrong.
5. **Simulation data never enters git.** Code, metadata, small derived catalogs,
   small figures only.
6. **Every figure traceable to run + code commit.** Use
   `amms.core.plotting.provenance.savefig`, never bare `plt.savefig`.
7. **Format-specific parsing stays in `codes/`.** `metadata.py` must not learn
   what AREPO is.
8. **Runtime deps stay few and light** — this must import on a login node in a
   bare module venv. Heavy readers (`yt`, `pynbody`) go in optional extras behind
   the backend that needs them.
9. **Two-tier validity.** pydantic checks schema on every read;
   `check_submit_ready()` separately reports blocking gaps. `amms submit --force`
   is allowed but records `forced: true` on the job entry, so an unlabeled run is
   a queryable field rather than an invisible one.

## HPC access (facts about this user's setup, not preferences)

- `ssh puma` → login node (junonia), via a bastion jump configured in
  `~/.ssh/config`. Use for submitting jobs, tailing logs, moving files.
- **junonia has no Lmod at all.** It is a *shared submission shell node* across all
  clusters (see `zz_ua_shellnode_only.sh`, `zz_ua_cluster_selector.sh` in its
  `/etc/profile.d`), so it cannot carry a per-cluster module stack. `module` is
  undefined there even in a login shell, and `LMOD_PKG`/`MODULESHOME` are empty.
  **Consequence: never run `bootstrap.sh` or `activate.sh` from junonia** — they
  take the no-`module` branch and print `assuming local machine`, which is a lie.
  The `shell` command belongs on the bastion (gatekeeper), not on junonia; the
  `(puma)` prompt prefix only means Puma is the selected *scheduler*.
- **Compute nodes have Lmod *and* outbound internet** (`pip install` from PyPI/git
  works there). `LMOD_PKG=MODULESHOME=/opt/ohpc/admin/lmod/lmod`, init script at
  `/etc/profile.d/lmod.sh` — so the `/opt/ohpc/admin/lmod/lmod` fallback already
  hardcoded in `bootstrap.sh` is correct, not dead code. Do env builds on the
  compute node, not junonia.
- `hpc-dev` (local `~/bin/hpc-dev`) allocates a compute node via
  `~/bin/vscode-hold.slurm` on junonia, rewrites `~/.ssh/hpc-dev` (included by
  `~/.ssh/config`), and points the `puma-dev` alias at whichever node was granted.
  **This is what VSCode Remote-SSH attaches to** for notebooks and interactive
  python. The hold job is named `vscode`.
- **Interactive sessions burn real allocation.** They end with `scancel -n vscode`.
  Never propose leaving one running, and prefer `sbatch` over interactive for
  anything that does not need a human in the loop.
- Current hold: 1 node, 4 CPUs, 4 hours, on a paid partition. **Windfall was
  rejected deliberately** — preemptible, and losing an interactive session
  mid-work is not worth the savings. Do not suggest it.
- SSH keys live on the shared home, so auth is keyless across nodes. Duo may still
  prompt about once a day.
- `~/.vscode-server/data/Machine/settings.json` on the cluster is tuned to avoid
  inotify watch limits and indexing CPU load. Don't propose settings that
  re-enable broad file watching.
- **Claude runs on the laptop only — never on the HPC.** There is no filesystem or
  shell access to Puma from a session. Propose shell commands and file contents
  for the user to paste into their Remote-SSH terminal; never assume a path on
  Puma can be read, and ask for output rather than inferring it.
- **`~/.venvs/amms` is a controlled environment. Do not install foreign
  dependencies into it.** Other people's code (the grad student's legacy analysis,
  pygadgetreader, the professor's old-simulation tooling) gets its own venv and its
  own Jupyter kernel. pygadgetreader may pin old numpy, which would downgrade the
  numpy in `env/locks/` and make the lock describe an environment that no longer
  exists — reproducibility lost to a convenience install.
- **`~/.venvs/legacy-gadget` is the built venv for legacy binary GADGET work**
  (built 2026-08-31 for Himansh Rathore's `clouds_demo` notebook; also the intended
  home for the professor's old-simulation tooling). Recipe, on a **compute node**:
  `module load python/3.14/3.14.2` → `python3 -m venv --upgrade-deps` →
  `pip install numpy matplotlib ipykernel` → plain
  `pip install git+https://github.com/jveitchmichaelis/pygadgetreader.git`.
  Installs as `pyGadgetReader 2.6` and pulls in `h5py`. **Do not pass
  `--no-build-isolation`** — the fork has a `pyproject.toml`, and py3.12+ venvs no
  longer seed `setuptools`, so the flag produces
  `BackendUnavailable: Cannot import 'setuptools.build_meta'`. numpy 2.x is fine;
  do not pin `<2`. `pip freeze` is recorded at
  `~/.venvs/legacy-gadget/freeze.txt`. py3.14 was chosen to match the notebook's
  saved `mypy14` kernel, which is the module python, not a conda env.

## Traps that have already cost time

- **UA's default python is 3.6.8 with no module**, where pydantic v2 and numpy
  1.24 cannot install. A failed `module load` therefore presents as a broken
  package, not a broken environment. `bootstrap.sh` asserts the version — keep it.
- **Distinguish a *failed* `module load` from an *absent* `module` command.** They
  present differently and the second one cost two debugging rounds: on junonia
  `module` does not exist at all (`bash: module: command not found`), which is a
  *node* problem, not a modules-misconfigured problem. `exec bash -l` does not fix
  it. Check `LMOD_PKG`/`MODULESHOME` and `ls /etc/profile.d/ | grep lmod` before
  proposing an init path to source.
- **A venv built on a module python breaks if that module isn't loaded.** Always
  `source env/activate.sh`, which does modules *and* venv. Never activate alone.
- **Jupyter kernels bypass `activate.sh` entirely and need a launcher wrapper.**
  VSCode's Jupyter extension reads `kernel.json` and **execs `argv[0]` directly
  from the Node extension host — no shell is ever in the ancestry.** `module` is a
  bash function, so the kernel can never have run `module load`; `LD_LIBRARY_PATH`
  lacks the module lib dir, and the venv's symlinked interpreter dies at
  `libpython3.X.so.1.0: cannot open shared object file`. This is a *dynamic loader*
  error with no Python traceback — the venv is fine, its environment is wrong, so
  rebuilding the venv is the wrong move. Fix: `argv[0]` points at a
  `kernel-launch.sh` that sources the Lmod init, `module purge && module load`,
  then **`exec`**s the venv python with `"$@"`. `exec` is required — without it bash
  lingers as parent and VSCode's interrupt/restart signals never reach python, so
  the stop button silently does nothing. `kernel.json` gets no shell expansion, so
  the path must be absolute (no `~`, no `$HOME`). Working example:
  `~/.venvs/legacy-gadget/kernel-launch.sh`. **Decision: wrapper, not a hardcoded
  `LD_LIBRARY_PATH` in `kernel.json`'s `env` key** — both work today, but the
  hardcoded path breaks on the next cluster image rebuild and presents as a corrupt
  venv. When `~/.venvs/amms` gets a kernel it wants the same wrapper, reading its
  module list from `env/modules.txt` so kernel and `activate.sh` cannot drift. That
  work is **not** blocked by the build freeze.
  Also: `ipykernel` auto-registers a duplicate `python3` kernelspec under
  `<venv>/share/jupyter/kernels/python3` pointing at the bare interpreter. It fails
  the same way and sits next to the working kernel in the picker.
- **pyGadgetReader's `Could not determine file type by extension!` means the file
  is unreadable, not that the extension is wrong.** It probes candidate filenames
  on disk (`snap`, `snap.0`, `snap.hdf5`, …) and emits this when none can be
  opened. Both a permission-denied path and a **leading space in the path string**
  produced it. Check `ls` on the path before touching format arguments, and never
  "fix" it by symlinking to an invented extension — if detection picks the wrong
  reader you get a successful read of garbage instead of an error.
- **pyGadgetReader calls `sys.exit()` on a missing particle type** (`no BULGE particles
  present!`). That raises `SystemExit`, which is a `BaseException` and is **not** caught
  by `except Exception` — so a loop over particle types dies silently mid-way and the
  remaining types are never reported. Cost one round of debugging. Catch
  `BaseException`, or order the loop so the types you need come first.
- Makefile recipes need literal tabs; VSCode inserts spaces by default.
- The local machine has no `pip` and no `ensurepip` (needs apt `python3-venv`,
  `python3-pip`). `bootstrap.sh` works on the cluster regardless.
- `os.replace` needs source and destination on the same filesystem — a temp file
  in `/tmp` renamed onto `/xdisk` raises `EXDEV`.

## Known limits, deliberately accepted

- `render_stub` handles our shapes only: scalars, flat dicts, string lists, nested
  models. `list[SubModel]` would render wrong. A round-trip test should pin this.
- Shell `ls` mis-sorts SIM_IDs past `_999`; `SimID` sorts numerically, so only raw
  `ls` is affected. Not worth widening the pad.
- `write_atomic` gives atomicity, not durability — no `fsync`. State is
  rebuildable by rescanning, so this is fine.
- NFS does not honor `O_APPEND` atomicity. If `events.jsonl` lines ever mangle,
  switch to one file per task under `events/`; the folding code globs.

## Open questions — ask, do not guess

- **When does the `/xdisk/gbesla` allocation expire?** Unanswered as of 2026-08-31,
  and it gates `hpc/storage.py`. Both the B12 comparison snapshots
  (`/xdisk/gbesla/group/`) and the user's own space live there, and `/xdisk` is
  deleted rather than archived. **More urgent as of 2026-09-04:** the only Puma clone of
  `clouds_demo` is at `/xdisk/gbesla/zvladimir/clouds_demo` (no home copy, not even a
  symlink), and `$AMMS_PRODUCTS` points at `/xdisk/gbesla/zvladimir/products`. A git
  repo does not belong on scratch — move it to `~/codes/`.
- Which of Puma / Lynx is primary, and whether Lynx is available yet. `machines.yaml`
  defines both; detection order is `AMMS_MACHINE` → `SLURM_CLUSTER_NAME` →
  hostname patterns → `local`. Never fall back to a raw hostname: this user's
  laptop has DHCP/Tailscale names that churn.
- The other grad student's analysis code has not been seen yet. `io/` carries a
  documented stub backend so it can slot in without touching call sites. Two
  *distinct* upstreams, do not conflate them: (a) **`snapAnalysis`**
  (github.com/hfoote/snapAnalysis, mostly Hayden Foote) is the group's **HDF5**
  reader for AREPO/GADGET-4 snapshots and the leading candidate for the real `io/`
  backend; (b) Himansh Rathore's code (`clouds_demo`) is the **legacy binary**
  pygadgetreader path. **(b) has now been read and reproduced** (2026-09-04) — see the
  B12 section above; its unit conversions, parent-ID decode and density center are all
  reproduced in `datasets/b12.py` and `analysis/frames.py`. Its `phi` recovery
  (`-arctan(abs(Ly/Lx))`) is quadrant-specific and correct only for the LMC's Q4 axis;
  `arctan2(Ly, Lx)` fixes it. **`snapAnalysis` still has not been read** and remains the
  candidate for the real `io/` backend.

## Commands

    source env/activate.sh        # modules AND venv — always both
    make dev                      # venv + editable install + pre-commit hooks
    make test | lint | fmt | check

## Build order

`codes/arepo.py` → `metadata.py` → `config/{machines.yaml,paths.py}` →
`io/{base.py,backends/}` → `plotting/{amms.mplstyle,provenance.py}` →
`analysis/cache.py` → `hpc/{slurm.py,storage.py,templates/}` →
`registry/scan.py` → `cli.py` last (thin wrapper over everything above).

`arepo.py` precedes `metadata.py` because `init_run()` and the drift check both
call into it. For actual progress, read `git log` and the file tree — this file is
not kept in sync with them.
