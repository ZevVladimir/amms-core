# amms-core

**AMMS = Arepo Milky-way Magellanic-clouds Simulations.** Shared core package pinned by
every AMMS project repo. A breaking change here silently invalidates old analyses —
treat the public API as load-bearing, version deliberately. Working style:
`~/.claude/CLAUDE.md`. The user keeps their own decision log; this file is mine.

**HYDRO runs with AREPO + SMUGGLE, NON-COSMOLOGICAL.** `ComovingIntegrationOn = 0`;
`TimeBegin`/`TimeMax` are physical times; `z_*`, `sigma_8`, `n_s`, `omega_*` are dead.
Never design around cosmological boxes (already made that error once). What
discriminates runs: galaxies present, masses, gas fractions, mass resolution, softening,
and the `SMUGGLE_*` block of `Config.sh`. Ladder: SMC → LMC → SMC+LMC → MW+SMC+LMC.

**ICs are the weakest provenance link** — upstream of this user, revised in place
(revision n and n+1 share a filename). Hash at time of use; it can't be backfilled.
AREPO may be built by someone else → copy `Config.sh` + compiler output into the run
dir; snapshot-embedded `/Config` is the authority. Matching group directory conventions
is **not** a goal.

**Claude runs on the laptop only, never on Puma.** Propose commands for the user to
paste; ask for output rather than inferring Puma state.

## Topic files — read the relevant one before working in that area

Path-scoped rules in `.claude/rules/` load automatically when matching files are touched:
- `b12.md` — B12 data locations, Model 2 ID blocks, ft==0 spike, 0.0488 pin, centring
- `maps.md` — Map2D seam, transpose pin, face-on rotation / `reference` convention
- `ics.md` — IC routes, registered hashes, box/grid shift facts, generator quirks
- `arepo-output.md` — run/snapshot layout, parser facts, first-run results

Notes in `.claude/notes/` are **not** auto-loaded — read on demand:
- `arepo-build.md` — compiling AREPO on Puma, systypes, modules, `test.py`
- `smuggle-config.md` — Config.sh flag sets, SMUGGLE params, the calibration blocker
- `hpc.md` — junonia vs compute nodes, venvs, Jupyter kernel wrapper, past traps

When a fact is learned, put it in the topic file it belongs to; this file keeps only
what every session needs. Delete superseded entries (git history keeps them).

## Freeze status

Rule: don't build a module whose design depends on runs/job patterns not yet seen.
Resume a frozen item only when its lift criterion is met, not because Build Order lists it.

- **Built / lifted:** `checks.py`, `ics.py` (fingerprint, budget, upstream hash, tag
  registry), `codes/makegalaxy.py`, `codes/arepo.py` *output parsing only* (usedvalues,
  config, sfr, cpu, Units), `analysis/` (numpy-only), `plotting/provenance.py`,
  `ids.py` (4-field SIM_ID + ExtID), `config/paths.py`, `products.py`,
  `tools/{check_snap,ic_sanity,plot_sfh,run_summary}` + dispatch-only `cli.py`.
- **Frozen, with lift criteria:**
  - `io/` — until snapAnalysis (github.com/hfoote/snapAnalysis, Hayden Foote; the
    group's HDF5 reader, leading backend candidate) is read and tested on real
    snapshots (wrap vs own). Not on the laptop yet.
  - `metadata.py` — until run #1 finishes incl. a restart *and* a second run's
    `metadata.yaml` is hand-written (fields seen generalising, not guessed).
  - `codes/arepo.py` build/submit wrapper + `provenance.py` (run-level submit-time
    capture: git, configs, modules, job id) — after manual build→submit→restart done twice.
  - `registry/`, `cli.py` scan/submit/init, dashboard — ~5 runs and restart-chain
    pattern settled. **Add those commands to `cli.py` once met.**
  - events.jsonl folding — only if Slurm task arrays happen. `_yamlio.py` has the
    primitives; build nothing on them.
- `provenance.yaml` vs events.jsonl for run provenance: still open.
- `hpc/storage.py` `/xdisk` expiry check: not frozen, blocked on knowing the expiry.

## Current state and next steps (updated 2026-11-10) — prune as items land

Puma layout: repos `~/{amms-core,smc,lmcsmcmw}`, upstream codes `~/codes/{arepo-smuggle,
arepo-grid}`, runs `~/sims -> /xdisk/gbesla/zvladimir/sims`, ICs + `ic_tags.yaml` in
`/groups/gbesla/zvladimir/ics`. Tags: `edw1`, `smct1`. Run #1 `smc_001_edw1_sh03` done
(1 Gyr, no restart). `lmcsmcmw` IS the `mwlmcsmc` project repo.

**Priority:** B12 (LMC/SMC SFH, SFR, gas, distances) analysis while own runs go, with
one analysis/plot code path for B12 and own runs: per-source loader → canonical arrays
in **kpc / km/s / Msun / Gyr** (AREPO `Units` gives Myr — add Gyr; state conventions on
load), B12 quirks in `datasets/b12.py`. Every function takes a snapshot.
- Distances: LMC–SMC and each-to-MW-centre, vs `datasets/patel2020.py` and other sims.
- Gas: within radius of LMC/SMC centre first; ID membership (incl. Stream) later —
  `selection` argument.
- SFH: present-day stellar ages (B12, drop ft==0) first, then own runs.
- B12 identity: `source_id` = SIM_ID or ExtID, equal standing in analysis/products/plots
  — proposed; user hasn't explicitly confirmed beyond adopting `ext_` dataset IDs.

**Active task:** LMC SFR(t) within 5 kpc, Model 2, snapshot_069. Batch
`lmcsmcmw/scripts/b12_lmc_newstars.py` → `ext_b12-model2/newstars_lmc-069.h5` (pos in
LMC frame, t_form_gyr, mass; ft==0 dropped at cache time); notebook
`notebooks/B12_SF_review.ipynb` (user's name) does radius cut + bins aligned to t_now.
Pin: all LMC stars, 100 Myr last bin ≈ 0.0488. **Target figure:** LMC–SMC distance vs t
/ SMC SFH / LMC SFH, one line per B12 model. Needs SMC cache, Model 1, and distance vs t
(many snapshots or `LS_MW/{LMC,SMC}.txt`).

**Next, in order:**
1. `GADGET_TIME_TO_GYR` → 0.9778 decided 2026-11-11 (see b12.md); transcribe + re-pin.
   Distance panel needs snapshot centres (`LS_MW/*.txt` is the IC orbit, see b12.md).
   Done 2026-11-12: `lmcsmcmw/scripts/b12_newstars.py` → `newstars_{lmc,smc}-069` for
   Model 2; notebook `b12_SF_review.ipynb`. Fid1 = Model 1, present day 069. Fig. 16 is
   10× ours, pipeline verified (b12.md) — user asks advisor. User's plot order: LMC SFH
   M2 5 kpc → LMC–SMC distance M2 → + galactocentric r → SMC SFR map M2 → SMC SFH M2 2 kpc.
2. `products.py` review fixes (proposed 2026-11-10): numpy-aware JSON `default` (current
   `default=str` turns `np.int64` into `"69"`, silent); dirty-repo warning like `savefig`.
3. `Map2D.save/load` → delegate to products (kind `sfrmap`); repoint
   `lmcsmcmw/scripts/{sfr_maps_b12,plot_sfr_maps,plot_radec}.py` (hardcode
   `products_root()/"b12_model2"`) at `ext_b12-model2`; regenerate, delete old dir.
4. `b12_lmc_newstars.py` → notebook; then SMC cache, Model 1.
5. `analysis/sanity.py` mass conservation (gas + new stars vs initial gas; M* vs sfr.txt).
6. First own-run figure: `amms plot-sfh` → `$AMMS_PRODUCTS/<sim_id>/figures/sfh_sfrtxt.png`
   (user-approved name; `_sfrtxt` leaves room for age-based `sfh_*`).
7. Snapshot maps over time, rotation curve, scale-height evolution (reading in drivers).
8. IC diagnostic plots (profiles vs analytic, rotation curve vs `.vc` — needs
   `makegalaxy.read_vc`, read source layout first — Toomre Q, Z/age) on edw1, smct1.
9. smc_test regeneration decisions (see `.claude/rules/ics.md`).
10. Archive policy for finished runs (only copy is on /xdisk).
11. Migrate `lmcsmcmw/scripts/plot_*.py` to `provenance.savefig`.
12. Hand-written `metadata.yaml` for run #1 (`status: done`, fill `<...>` fields).
13. Puma checks asked 2026-11-10: PartType4 `StellarFormationTime` without STELLARAGE;
    rental snapshot_069 sha256 vs xdisk copy (which dir is Model 2); `LS_MW/*.txt` heads;
    `/xdisk` expiry.

**"Where is everything" (user, 2026-11-06):** products/figures → products attrs +
`build_catalog` (+ `amms where`); everything else → generated layout map (`amms layout`)
walking `machines.yaml` roots. Not frozen. Vault on desktop, Syncthing-synced → Puma
writes one md, laptop rsyncs into the vault (vault path still needed). No scrontab →
`amms layout || true` as the last line of every job script. Proposed output
`~/amms-layout/LAYOUT.md`.

**IC generation becomes its own package later.** Core keeps inspection (`ics.py`) and
read-only format parsing (`codes/makegalaxy.py`). Generator modules expose
`component_budget(params) -> list[ExpectedComponent]`. IC sanity products live with the
IC: `<ics_root>/<ic_name>/sanity/`, symlinked from `$AMMS_PRODUCTS/ics/<ic_name>`;
results carry the IC sha256. IC figures → `sanity/<ic_stem>/figures/` (user, 2026-11-13;
filenames not yet approved). Wanted: profiles vs analytic, v_c vs `.vc`, Toomre Q +
vertical, maps + Z/age. Result plots after: SFH sfrtxt, maps over time, v_c evolution,
scale height/Q evolution — share code paths with the IC plots.

## Citing upstream source

Always `<checkout>:<path from checkout root>:<line>`, never a bare filename (the two
AREPOs share most filenames). Line numbers are against these commits:

| Alias | Location | Commit | Language |
|---|---|---|---|
| `arepo-smuggle` | `~/codes/arepo-smuggle` (laptop read-only + Puma) | `Arepo2-smuggle-mod` d323be6; Puma `puma-buildsystem` changes only `buildsystem/` | C++ |
| `arepo-grid` | Puma `~/codes/arepo-grid`; laptop `~/smc/ics/make_ics_from_ethan/arepo_grid` (unpatched) | `master` f18a5b80a3 (+ gas-only shift patch on Puma, same lines) | C |
| `makegalaxy` | `/groups/.../ics/make_ics_from_ethan/MakeGalaxy`; laptop `~/smc/ics/make_ics_from_ethan/MakeGalaxy` | no git; source of `MakeGalaxy_new`, **not** of `MakeGalaxy_puma9_modified_bulge` | C |

## Settled — argue only with new evidence, and name the decision if you do

- AREPO only; GADGET-style HDF5 snapshots. h5py is the default IO backend;
  pygadgetreader is an alternate for legacy binary (unmaintained).
- Slurm on UA HPC: **Puma and Lynx**. Ocelote/El Gato are decommissioned — never propose
  or add them. Tiers: `/home`, `/groups`, `/xdisk` (expires, **deleted**), `/rental`
  (long-term, no compute), `/tmp` (node-local). Stage to `/tmp` for repeated reads; keep
  files-per-dir in the hundreds.
- PI/group `gbesla`; HPC user `zvladimir`, home `/home/u2/zvladimir`.
  `/xdisk/gbesla/group/` is shared read-only comparison data. Others' `/xdisk/gbesla/<netid>/`
  are not readable.
- **Site python module + venv, never conda.** Reproducibility = `env/modules.txt` +
  committed `env/locks/<cluster>-py<ver>.txt` (one per cluster/python pair).
  `requires-python >= 3.10`; `modules.txt` pins 3.11.4; 3.14 existing doesn't reopen it.
- `amms` namespace package; never create `src/amms/__init__.py` (reserves `amms-viz`).
- pydantic v2 with `extra="forbid"` on every model.
- Four project repos, one per galaxy configuration (`smc`, `lmc`, `lmcsmc`, `mwlmcsmc`),
  four run counters. Do not reopen.
- **SIM_ID = `<project>_<NNN>_<ic>_<slug>`** (`smc_001_edw1_sh03`). `NNN` per project
  across ICs. `ic` matches `IC_TAG_RE` `^[a-z]+[0-9]+$` (in `ids.py`); existence + sha256
  via `ics/ic_tags.yaml` / `ics.check_ic_tag`. Tags never reused, one tag = one file. A
  run resumed from another run's snapshot carries the root IC tag; parent in
  metadata.yaml. No physics prefix. `parse()` round-trips: one spelling per identity.
- **Puma layout:** own repos `~/`, upstream codes `~/codes/`, runs
  `<xdisk_own>/sims/<project>/<sim_id>/` via `sims_root()`. `arepo-smuggle/run` only for
  AREPO's own `test.py`.
- **Products:** parallel tree `$AMMS_PRODUCTS/<dataset_id>/`, not in run dirs. dataset_id
  = SIM_ID or `ext_<slug>` (`ext_b12-model2`, `ext_b12-model1`; reserves project name
  `ext`; lets the release script refuse externals). Files flat
  `<kind>_<qualifier>.h5`, kind from fixed `KINDS`, qualifier hyphenated slug
  (`newstars_lmc-069.h5`). Centre tracks: kind `orbit`, one file per galaxy
  (`orbit_lmc.h5`: snapshot, t_gyr, pos_kpc, vel_kms); distances derived at plot time
  (user, 2026-11-11).
- **Products are release-shaped HDF5 from birth** with required provenance attrs,
  pydantic-validated. Release = select + freeze + copy, never conversion. Do not reopen
  HDF5-everywhere. h5py lazy inside `products.py`.
- **Generic drivers live in `amms.core.tools`** (users are user + group, so API cost is
  low); `cli.py` dict-dispatches to `tools.<module>.main(argv)`, each tool owns its
  argparse (`prog="amms <cmd>"`). Project-specific drivers and `bin_hdf_conv.py` stay in
  project repos.
- One app, two catalogs: `amms-viz`, Panel/HoloViz (`panel convert` → static Pyodide
  site). Reads catalog + products only. Frozen; the product contract is not.
- Releases go to `/groups` or `/rental` + Zenodo, never `/xdisk`. `ext_*` never released
  without owner permission. PI sign-off is a human step.

## Invariants — violating these is a bug

1. `ids.py` and `metadata.py` import nothing else from this package.
2. **No `save_metadata()`, ever.** `metadata.yaml` is human-curated (yaml.dump drops
   comments). `amms` writes only `state.yaml` and `events.jsonl`; `init_run()` writes the
   stub once and refuses to overwrite. Enforcement is the function's absence.
3. Jobs never read-modify-write shared state: one `os.write` line to `events.jsonl` on an
   `O_APPEND` fd; `amms scan` folds from one process.
4. No hardcoded cluster paths outside `machines.yaml`; resolve via `config.paths`.
5. Simulation data never enters git.
6. Every figure via `plotting.provenance.savefig`, never bare `plt.savefig`.
7. Format-specific parsing stays in `codes/`.
8. Runtime deps few and light (imports on a login node in a bare module venv); heavy
   readers in optional extras.
9. Two-tier validity: pydantic on read; `check_submit_ready()` reports blocking gaps;
   `submit --force` records `forced: true`.
10. Products written only through `amms.core.products`, never bare `np.savez`/`h5py.File`.

## Known limits, deliberately accepted

- `render_stub` handles scalars, flat dicts, string lists, nested models only;
  `list[SubModel]` renders wrong.
- Raw `ls` mis-sorts SIM_IDs past `_999` (`SimID` sorts numerically).
- `write_atomic`: atomicity, not durability (no fsync); state is rebuildable.
- NFS doesn't honour `O_APPEND` atomicity; if events.jsonl mangles, one file per task.

## Open questions — ask, do not guess

- **When does `/xdisk/gbesla` expire?** Gates `hpc/storage.py`. B12 copy, own runs and
  `$AMMS_PRODUCTS` all live there. The only Puma `clouds_demo` clone is at
  `/xdisk/gbesla/zvladimir/clouds_demo` — move it to `~/codes/`.
- Puma vs Lynx primary; is Lynx available. Detection: `AMMS_MACHINE` →
  `SLURM_CLUSTER_NAME` → hostname patterns → `local`; never a raw hostname.
- Baseline: professor's older runs as read-only `ext_` entries — eventually, not now.

## Commands

    source env/activate.sh        # modules AND venv — always both
    make dev | test | lint | fmt | check
    # laptop: ~/.venvs/amms/bin/python -m pytest -q

## Build order (remaining)

Product track: `Map2D` delegate → regenerate B12 products → `build_catalog` once a
second dataset has products → release script → `amms-viz` (frozen). Core track, as
freezes lift: `metadata.py` → `io/` → `analysis/cache.py` → `hpc/{slurm,storage}.py` →
`registry/scan.py` → remaining `cli.py` commands. `arepo.py` build wrapper precedes
`metadata.py` (`init_run()` and drift check call it). Read `git log` for actual progress.
