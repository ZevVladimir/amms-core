# HPC access, environments, traps

Read before proposing shell commands for Puma, venv/kernel changes, or env debugging.

## Access

- `ssh puma` → junonia via bastion. Submit jobs, tail logs, move files.
- **junonia has no Lmod** (shared submission node across clusters). Never run
  `bootstrap.sh`/`activate.sh` there — they print `assuming local machine`, a lie.
- **Compute nodes have Lmod and outbound internet** (pip works).
  `LMOD_PKG=MODULESHOME=/opt/ohpc/admin/lmod/lmod`, init `/etc/profile.d/lmod.sh` — the
  fallback in `bootstrap.sh` is correct. Build envs on compute nodes.
- `hpc-dev` (`~/bin/hpc-dev`) allocates a node via `~/bin/vscode-hold.slurm`, rewrites
  `~/.ssh/hpc-dev`, points `puma-dev` at it; VSCode Remote-SSH attaches there. Hold job
  name `vscode`; 1 node, 4 CPUs, 4 h, paid partition. **Windfall rejected deliberately**
  (preemptible) — don't suggest it. End with `scancel -n vscode`; never propose leaving
  one running; prefer `sbatch`.
- **New-machine setup lives in `github.com/ZevVladimir/dotfiles` (private, `~/dotfiles`)**:
  README steps, `ssh/config.puma` (Included from `~/.ssh/config`, not copied),
  `bin/hpc-dev` (symlinked), reference copy of `puma/vscode-hold.slurm`. Point users
  there; edit the repo, not per-machine copies. Desktop (`zvladimi@…whitenoisemachine4000`)
  set up 2026-11-11; hang there was a hand-copied `puma` block missing `ProxyJump`.
  Laptop still uses inline blocks + `~/bin/hpc-dev` with the `[[ -S glob ]]` bug
  (never auto-opens VSCode) until migrated.
- SSH keys on shared home; Duo ~daily. Cluster VSCode settings are tuned against
  inotify limits — don't re-enable broad watching.
- **scrontab is not enabled on UA.**

## Environments

- `~/.venvs/amms` is controlled — **no foreign deps** (pygadgetreader may pin old numpy
  and make `env/locks/` lie). Its `activate.sh` purges modules → keep it in a different
  shell from a run's AREPO `env.sh`.
- `~/.venvs/legacy-gadget` (py3.14 module, matches `mypy14` kernel): on a compute node,
  `module load python/3.14/3.14.2` → `python3 -m venv --upgrade-deps` →
  `pip install numpy matplotlib ipykernel` →
  `pip install git+https://github.com/jveitchmichaelis/pygadgetreader.git`
  (pyGadgetReader 2.6, pulls h5py). **No `--no-build-isolation`** (py3.12+ venvs lack
  setuptools → `BackendUnavailable`). numpy 2.x fine. Freeze at `freeze.txt`.
  amms-core installed with `pip install -e <repo> --no-deps`.
- `~/.venvs/arepo-tests` for AREPO's `test.py`.

## Traps that already cost time

- UA default python is 3.6.8 → failed `module load` looks like a broken package.
  `bootstrap.sh` asserts the version.
- Failed `module load` ≠ absent `module` command (`command not found` = wrong node).
  Check `LMOD_PKG`/`MODULESHOME` and `/etc/profile.d/` before proposing an init path.
- A module-python venv breaks if the module isn't loaded: always `source env/activate.sh`.
- **Jupyter kernels bypass the shell**: VSCode execs `kernel.json` `argv[0]` directly,
  so `module load` never ran → `libpython3.X.so.1.0: cannot open shared object file`
  (loader error, venv is fine). Fix: `argv[0]` = absolute path to a `kernel-launch.sh`
  that sources Lmod init, `module purge && module load`, then **`exec`**s the venv python
  `"$@"` (without `exec`, interrupt/restart never reach python). Example
  `~/.venvs/legacy-gadget/kernel-launch.sh`. Decision: wrapper, not hardcoded
  `LD_LIBRARY_PATH` in `kernel.json`. An amms kernel would read `env/modules.txt`; not
  frozen. `ipykernel` also registers a broken duplicate `python3` kernelspec in the venv.
- pyGadgetReader `Could not determine file type by extension!` = file unreadable
  (permissions, leading space in path). `ls` first; never symlink to an invented extension.
- pyGadgetReader `sys.exit()`s on a missing particle type → `SystemExit` escapes
  `except Exception`. Catch `BaseException` or order types.
- Makefile recipes need literal tabs. Laptop has no `pip`/`ensurepip`.
- `os.replace` across filesystems (`/tmp` → `/xdisk`) raises `EXDEV`.
