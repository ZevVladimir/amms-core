# amms-core

**AMMS = Arepo Milky-way Magellanic-clouds Simulations.** The science is the Milky
Way and the Magellanic Clouds: satellite dynamics, LMC/SMC orbits and interaction,
stellar streams. Expect `analysis/` to grow toward halo/satellite finding, orbit
integration and stream diagnostics rather than, say, cosmological power spectra.

Shared core package pinned by every AMMS project repo. AREPO simulations, UA HPC,
Slurm. A breaking change here silently invalidates old analyses, so treat the
public API as load-bearing and version deliberately.

Working style: `~/.claude/CLAUDE.md`. The user keeps their own decision log and
relies on it primarily; this file is mine, and exists so I stop re-deriving or
relitigating settled calls.

## Settled — argue only with new evidence, and name the decision if you do

- **AREPO** is the only simulation code. GADGET-style HDF5 snapshots.
- **Slurm on UA HPC.** Tiers: `/home`, `/groups`, `/xdisk` (time-limited
  allocation — expires and is *deleted*), `/rental` (long-term, must not compute
  from it), `/tmp` (node-local, cleared at job end). Site guidance: stage to
  `/tmp` for repeated reads, keep files-per-directory in the hundreds not tens of
  thousands, avoid tight open/close loops.
- **Site python module + venv. Never conda/mamba.** Consequence:
  `environment.yml` cannot describe this environment, so reproducibility rests on
  `env/modules.txt` + committed `env/locks/`.
- **`amms` namespace package**; this repo owns `amms.core`. Never create
  `src/amms/__init__.py` — its absence is what allows a future `amms-viz`.
- **pydantic v2 with `extra="forbid"` on every model.** Forbid is the point:
  `phyics: hydro` would otherwise parse cleanly and leave `physics` as None.
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
- **`requires-python = ">=3.10"`.** Cluster module tops out at 3.11.4; avoid
  3.11-only syntax so the floor stays honest.
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

## Traps that have already cost time

- **UA's default python is 3.6.8 with no module**, where pydantic v2 and numpy
  1.24 cannot install. A failed `module load` therefore presents as a broken
  package, not a broken environment. `bootstrap.sh` asserts the version — keep it.
- **A venv built on a module python breaks if that module isn't loaded.** Always
  `source env/activate.sh`, which does modules *and* venv. Never activate alone.
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

- PI/group name (the `/groups/<PI>` and `/xdisk/<PI>/<user>` component) and the
  HPC username (likely `zvladimir`). Needed for `config/machines.yaml`.
- Which cluster(s) they primarily use. Plan: define all three, Puma default,
  detect via `AMMS_MACHINE` → `SLURM_CLUSTER_NAME` → hostname patterns → `local`.
- Whether this AREPO build embeds `/Config` and `/Parameters` HDF5 groups in
  snapshots (`h5ls -r <snap> | grep -iE '^/(Config|Parameters)'`). If yes those
  are the authoritative provenance source and `param.txt` becomes the fallback.
- The other grad student's analysis code has not been seen yet. `io/` carries a
  documented stub backend so it can slot in without touching call sites.

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
