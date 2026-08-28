# amms-core

This is the shared core package for my PhD simulation projects that use AREPO to simulate the Milky Way and Magellanic clouds
(Arepo Milky-way Magellanic-clouds Simulations)

Each project pins a version allowing for reproducibility and consistency

## Install
```
git clone <url> && cd amms-core
make dev # sets up the modules, venv, editable install, pre-commit hooks
```

Then to activate the environment: load in the pinned modules and activate the venv
Do NOT just activate the venv alone
```
source env/activate.sh
```

## Run identity
Every simulation is assigned one `SIM_ID`, of the form: `<project>_<NNN>_<slug>`
This is used for the run directory name, metadata key, registry row, Obsidian note, figure file name, etc.

Each run directory contains three files:
| File | Owner | Notes |
|---|---|---|
| `metadata.yaml` | you | Hand-curated. `amms` only ever reads it, so comments survive. |
| `state.yaml` | `amms` | Rewritten on every submit/scan. Do not hand-edit. |
| `events.jsonl` | jobs | Append-only. Array-job safe; `amms scan` folds it into state. |

Cached analysis products are kept outside the run directory. Generally in `$WORK/products/<sim_id>/` to keep datasyncs small and independent of snapshots

## Layout
| Path | Purpose |
|---|---|
| `ids.py` | `SIM_ID`: parse, validate, allocate |
| `metadata.py` | `metadata.yaml` / `state.yaml` schema and IO |
| `codes/` | simulation-code-specific parsing (AREPO `param.txt`, `Config.sh`) |
| `config/` | machine detection and path resolution — no hardcoded cluster paths |
| `io/` | snapshot reading; swappable backends, h5py by default |
| `analysis/` | cached derived products |
| `plotting/` | shared mplstyle + provenance-stamping `savefig` |
| `hpc/` | Slurm job rendering and submission, storage/archive helpers |
| `registry/` | scan run directories into a searchable index |

## Development
```
make # list the available targets
make test
make check
```

### AI Usage
Claude is used to help plan and propose code and design structure. Claude does not make any edits to any documents besides CLAUDE.md and other claude specific files. All edits are typed in by a human.

## Status
Pre-1.0. API unstable
