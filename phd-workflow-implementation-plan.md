# PhD research workflow — implementation handoff

## How to use this document (read first, you are the assistant)

You are helping a computational astrophysics PhD student set up their research
organization system from scratch. This document is a handoff from a prior
conversation where the overall architecture was designed. Your job is to help
**implement** it, step by step.

Before writing any simulation-reading or analysis code, **confirm the open
decisions in the "Confirm before coding" section** — several implementation
details (especially snapshot I/O) are undetermined until those are answered.
Do not guess the simulation code or snapshot format.

Work incrementally. Build one component at a time, get it working, then move on.
The person is comfortable with Python, VSCode, git, and HPC, so you can be
technical, but they are early in the PhD and want maintainable defaults, not a
sprawling framework. Prefer thin wrappers over community tools rather than
reimplementing standard functionality.

---

## Who the person is / their situation

- Computational astrophysics PhD, work is **almost entirely computational**.
- Heavy **HPC usage**; runs **many simulations**. Most work happens on the HPC;
  some light work on a laptop/desktop.
- Simulations **build on one another**: starting with **N-body**, progressing to
  **fully hydrodynamic**. Later stages need extra analysis modules and much more
  storage.
- Writes a lot of code: running sims, analyzing sims, making figures. Wants code
  that is **flexible and reusable**.
- Editor/workflow: **VSCode with Remote-SSH into the HPC**. **Jupyter notebooks
  primarily for plotting**; **heavier analysis in standalone scripts** (batch
  jobs).
- Tools already in use / planned: **Obsidian** (notes/log, likes it but wants
  better structure), **Zotero** (references), **Overleaf** (paper writing,
  chosen for collaboration + Zotero + git integration).
- Open to **building tools**; specifically wants a **simulation dashboard** with
  interactive plots + searchable sim info (found one invaluable in a past
  project).
- Pain points to solve: losing track of simulations; losing track of papers;
  inconsistent notes; no clean reproducibility chain from figure back to run.

---

## Core design principles (these are settled — do not relitigate)

1. **Separate the five layers**: code (small, in git) / data (huge, on HPC, never
   in git) / metadata (the bridge) / notes / prose. Keep them distinct.
2. **Thread one `SIM_ID` through everything** — the run directory, its metadata
   file, the registry/dashboard, the Obsidian note, and figure filenames/
   captions. Any figure must be traceable to the exact run + code commit.
3. **Thread one `CITEKEY` through the literature side** — stable citation keys
   from Zotero flow into Obsidian reading notes and into Overleaf.
4. **Metadata travels with the data**; the searchable index is *derived and
   rebuildable* from it (so it can never silently drift out of sync).
5. **Reusable code is a real installed package**, not scripts copied between
   projects. Fix a bug once, everyone benefits.
6. **Don't reinvent snapshot I/O** — wrap an existing community library.
7. **Compute → cache → plot**: heavy scripts (batch jobs) write intermediate
   products to disk; notebooks only load those and plot. Notebooks stay light.

---

## Target architecture

**Two spines** connect the tools:

- Compute spine (keyed by `SIM_ID`):
  HPC storage (sim data + `metadata.yaml` per run) → scanner → registry →
  dashboard. A shared **core package** is imported by every project repo and is
  what reads snapshots and makes standard plots.
- Literature spine (keyed by `CITEKEY`):
  Zotero (collections = projects, tags = themes) → Better BibTeX `.bib` export →
  Overleaf. Figures (stamped with `SIM_ID`) also flow into Overleaf.
- Obsidian sits in the middle, with a note per `SIM_ID` and reading notes that
  reference `CITEKEY`, connecting "why/what I learned" to "what it is / where the
  data is."

**Repos:**
- One **core/utility package** (installable, versioned): `io/`, `analysis/`,
  `plotting/`, `hpc/`, `config/`, `tests/`.
- **One repo per project** (separate — independent lifecycles), importing a
  pinned version of the core package. Layout:
  `config/`, `scripts/` (heavy, batch), `notebooks/` (light, plotting),
  `src/<projname>/`, `figures/`, `paper/` (Overleaf-synced), plus `README.md`
  and a pinned `environment.yml`.

---

## Confirm before coding (ask the person these)

Snapshot I/O and job scripts depend entirely on these — do not proceed to
Phase 2's I/O module until answered:

1. **Which simulation code(s)?** (e.g. Gadget-4, AREPO, SWIFT, GIZMO, RAMSES,
   Enzo, ChaNGa, …) This fixes the snapshot format and the right reader library.
2. **Preferred analysis library?** Options: `yt` (general, multi-code),
   `pynbody`, `swiftsimio` (if SWIFT), `nbodykit`, `pygad`. The core `io/` module
   should wrap the chosen one.
3. **HPC details**: scheduler (Slurm / PBS / LSF / SGE?), any policy limiting the
   VSCode remote server or running on login nodes, and whether jobs run through
   an interactive session or pure batch.
4. **Storage tiers + purge policy** on their cluster (scratch vs project vs
   archive; how long untouched scratch survives). This drives the "persist
   keep-worthy outputs" routine.
5. **Python environment tool**: `mamba`/`micromamba` vs the cluster's module
   system + venv (or a mix).
6. **GitHub setup**: personal account vs an org/group; repos private by default?
   Naming convention for repos.
7. **Naming scheme** for `SIM_ID`: date-based, sequential, or hash + human tag.
   Propose one and get sign-off before baking it into the metadata schema.

---

## Implementation order

The three items marked **[CRITICAL]** cause irreversible pain if skipped or
delayed; prioritize them. Do **not** over-build the registry/dashboard early —
start with flat files and a small scanner; add SQLite + dashboard only once run
count justifies it.

### Phase 1 — Foundations
- **[CRITICAL] Environment management.** Establish the chosen env tool and a
  pinned per-project `environment.yml` pattern. Nothing is reproducible without
  this.
- **[CRITICAL] Storage/persistence routine.** Confirm purge policy; define a
  simple habit/script to move keep-worthy outputs + their metadata to persistent
  storage after a run finishes.
- **SSH/VSCode setup.** `~/.ssh/config` with a host alias, `ControlMaster` +
  `ControlPersist` (avoid repeated 2FA), `ProxyJump` if there's a gateway.
  Confirm cluster policy on the VSCode remote server.

### Phase 2 — Core package
- **[CRITICAL] Make it a real installable package.** `pyproject.toml`, `src/`
  layout, install editable (`pip install -e .`), version + tag it.
- Structure: `io/` (thin wrapper over the chosen snapshot library),
  `analysis/` (profiles, densities, common measurements), `plotting/` (styled
  functions + a shared `.mplstyle`), `hpc/` (Slurm/job-script generation, path
  resolution), `config/` (machine-aware paths — no hardcoded `/scratch/...`),
  `tests/`.
- Start `io/` only after the sim code + library are confirmed.
- Add a couple of tests early so later refactors don't silently break analysis.

### Phase 3 — Project template
- Build a **cookiecutter** (or copier) template producing the per-project layout
  above, with `pyproject.toml`/`environment.yml` pinning the core package,
  `.gitignore` (exclude data + notebook output), and a README stub. High payoff,
  do this early.
- **Notebook hygiene:** set up `jupytext` (pair notebooks with `.py`/`.md` for
  clean diffs) or at least `nbstripout` on commit.

### Phase 4 — Metadata + lightweight registry
- Define the `metadata.yaml` schema: `SIM_ID`, physics type (nbody/hydro),
  resolution, box size, key parameters, code version/commit, date, status,
  storage path, one-line description. It lives **in the run directory**.
- Write a scanner that walks storage, reads every `metadata.yaml`, and builds a
  pandas DataFrame (cache to parquet). This is enough to search sims initially.

### Phase 5 — Reference management (Zotero)
- Collections = projects (items can live in multiple collections). Tags =
  cross-cutting themes/methods/status. Saved searches for dynamic groups.
- Install **Better BibTeX**: set a stable citekey format; configure auto-export
  of a per-project `.bib` (this is the `CITEKEY` bridge to Overleaf/Obsidian).

### Phase 6 — Notes (Obsidian)
- Folder structure: `Projects/`, `Areas/`, `Literature/`, `Daily/`, `Meetings/`.
- Daily note = the running log ("what I did / changed / results / questions /
  TODOs"), automated via Templater.
- Note-per-simulation template referencing `SIM_ID`; reading-note template
  referencing `CITEKEY`.
- Plugins: Dataview, Tasks, Templater, a Zotero integration plugin, optionally
  MOCs for cross-project links. Put the vault in a private git repo.

### Phase 7 — Paper pipeline (Overleaf)
- Use Overleaf's git integration so the `paper/` in the project repo syncs.
- Overleaf pulls the Better BibTeX `.bib`; figures flow in from `figures/`.
- **Stamp provenance**: encode `SIM_ID` + code commit in figure metadata or
  filenames so every figure in the paper is traceable.
- Mention `showyourwork` (Snakemake-based, astro-oriented) as an *optional*
  later step for full paper reproducibility — not day one.

### Phase 8 — Registry + dashboard (only when justified)
- Promote the Phase 4 scanner output into a **SQLite** index (still rebuildable
  from the `metadata.yaml` files).
- Build a **dashboard** (Streamlit for speed, or Panel/HoloViz for richer
  interactive plots on large data) that reads the registry, lets the person
  filter/search sims, and shows precomputed **thumbnail** diagnostic plots
  (precompute in the post-run pipeline — never compute on huge data live).
  Registry + thumbnails are small enough to sync to a laptop and run locally.

---

## Deliverables the person may ask you to build

- Cookiecutter project template (Phase 3).
- Core-package skeleton with `metadata.yaml` schema + scanner (Phases 2 & 4).
- Streamlit/Panel dashboard skeleton reading a registry (Phase 8).
- Obsidian starter vault (folders + daily/sim/reading note templates + Dataview
  examples) (Phase 6).
- `~/.ssh/config` + Slurm job-script template for the VSCode↔HPC workflow
  (Phases 1 & 2).

Build whichever the person picks; produce real files, not just snippets.

---

## Conventions to keep consistent

- Data never in git; only code, metadata, small derived catalogs, and (small)
  figures.
- One `SIM_ID` and one `CITEKEY` scheme, used everywhere.
- Pinned environments per project; pin the core package version too.
- Notebooks light (load + plot); heavy work in scripts run as batch jobs.
- Every figure traceable to run + commit.
