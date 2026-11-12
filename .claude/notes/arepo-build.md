# AREPO on Puma — build facts (established 2026-09-01)

Read before proposing anything about building AREPO, systypes, modules, or `test.py`.

- **Source:** `git@bitbucket.org:volkerspringel/arepo.git`, branch `Arepo2-smuggle-mod`
  (`d323be6`, Marinacci, 2026-07-20). Private, SSH key auth, port 22 open from compute
  nodes. 17 SMUGGLE branches; `lucchini_smuggle` is Magellanic-relevant and was *not*
  chosen. Clone `~/codes/arepo-smuggle` on Puma (local branch `puma-buildsystem`,
  changes only `buildsystem/`), read-only copy on the laptop.
- **`git clone --recurse-submodules` is mandatory** (`lib/safeintegral`). Without it
  every compile fails, and under `make -i` that prints `Error 127 (ignored)` and links
  zero objects — looks like a linker problem.
- **AREPO2 is C++** (`src/main/main.cc`). Systype must set **both `CC` and `CPPC`** to
  `mpicxx -std=c++11`, no `-std=c11` in `OPTIMIZE`. Unset `CPPC` execs `-std=c11`.
- **Upstream `SYSTYPE="Puma"` was dead** (hardcoded 2020 module paths, no CC/CPPC).
  Fixed on `puma-buildsystem`; worth upstreaming.
- **Stack:** default `gnu13/13.2.0 openmpi5/5.0.5 hwloc/2.13.0 ucx libfabric`; under
  gnu13 `gsl/2.7.1 hdf5/1.14.0`; under gnu13-openmpi5 `fftw/3.3.10 phdf5/1.14.0`. Build
  set: `gnu13 openmpi5 gsl hdf5 fftw`.
- **Use module `*_DIR`/`*_INC` vars, never literal paths.** `FFTW_LIB` and `HWLOC_LIB`
  are assigned in `Makefile` before `systypes.make`, shadowing the module env
  (`-L$(HWLOC_LIB)` → `-L-lhwloc`).
- `GMPLIB := -lgmp` is unconditional. FFTW linked only under `PMGRID`/`TURB_POWERSPEC`,
  HWLOC only under `IMPOSE_PINNING` — irrelevant for non-cosmological runs.
- **No `-march=native`**: mixed node generations → `Illegal instruction`.
- **One binary per run dir:** `make TARGET_DIR=<dir>` reads `<dir>/Config.sh`, writes
  `<dir>/Arepo` + `<dir>/build/`. That *is* the copy-Config-into-run-dir decision — wrap
  it in `codes/arepo.py` later, don't reimplement. Build with
  `make TARGET_DIR=~/sims/<project>/<sim_id>`.
- **Test framework:** `./test.py --no-cleanup shocktube/shocktube_sod_1d` (names are
  paths under `examples/`). Output `<repo>/run/examples/<name>/`. Lives in
  `~/.venvs/arepo-tests`, **not** `~/.venvs/amms`. `code_tests.md` mentions a
  nonexistent `test.sh`.
- Docs worth reading before guessing: `documentation/{getting_started,code_tests,
  core_param_options,core_unit_system,modules_smuggle_sfr}.md`. No SMUGGLE example ships.
