---
paths:
  - "src/amms/core/codes/arepo.py"
  - "src/amms/core/tools/**"
  - "src/amms/core/analysis/sanity.py"
  - "tests/test_arepo.py"
  - "tests/test_sanity.py"
---

# AREPO output — observed, not guessed

## Run directory and snapshot layout (confirmed 2026-09-01 / 2026-11-02)

- Run dir: `Arepo`, `build/`, `Config.sh`, `param.txt`, `param.txt-usedvalues`,
  `ics.hdf5`, `uses-machines.txt`, `output/`, per-run `env.sh`.
- `output/`: `snap_NNN.hdf5`, `restartfiles/`, `end`, logs `balance cpu domain energy
  hostmemory info memory timebins timings .txt` (+ `sfr.txt` with SFR on).
- **Snapshots embed `/Config` and `/Parameters`** — authoritative provenance;
  `param.txt` is the fallback.
- **`<paramfile>-usedvalues`** is written to the **run dir root**, not `OutputDir`, and
  includes AREPO's defaults.
- **The parameter set is a function of `Config.sh`** (62 params for the 1D sod test).
  So `metadata.py` must not enumerate AREPO parameters.
- **`output/end`** is an empty file on clean termination — the completion sentinel for
  a future `registry/scan.py`.
- `cpu.txt` was 4.4 MB for a 100-cell 1D test with `DEBUG` + `TimeBetStatistics 0.01` —
  an upper bound on verbosity, not a size estimate.

## Parser facts (`codes/arepo.py`, tests built from upstream printf formats)

- `read_config` must skip the `AREPOCONFIG_H` include guard (was returned as a flag).
- **sfr.txt col 6 (`cum_mass_stars`) is a file-static that resets on every restart**
  (`arepo-smuggle:src/cooling_sfr/starformation.cc:47`) → `read_sfr` rebuilds it as
  `cumsum(col 5)`. Validated on sh03 (4e-7 rel, no restart).
- Laptop copy of sh03 sfr.txt: `~/arepo-sims-output/sfr.txt` (no usedvalues beside it).
- cpu.txt cumulative-across-restarts is **unverified** — no restart has happened yet.
- Binned SFH uses `analysis.sfr.sfh` on per-step mass, never interpolation of the
  cumulative.

## Tools

- Tools pass `repo=Path(__file__).parent` to `savefig`: under the console script
  `__main__` is the venv wrapper, so default provenance would record `code: None`.
- A new star sits on its parent cell's position → cross-type duplicate positions are
  expected (`unique_all` is WARN, not FAIL).

## First run: `smc_001_edw1_sh03`

`/xdisk/gbesla/zvladimir/sims/smc/smc_001_edw1_sh03` (moved 2026-11-05 from
`arepo-smuggle/run/ethan_dwarf_1e6/sh03`; `check_ic_tag` PASS after move). SH03 dry run
on `edw1`.
- Needed `OVERRIDE_PEANOGRID_WARNING`: without it the domain top-tree terminates at SFR
  onset (one unsplittable node, 4% of work, 76x limit; IC had no duplicate positions, so
  it develops in-run; mechanism unproven).
- Smoke 10 Myr: 22.6 min on 94 tasks. **Full 1 Gyr in ONE 48 h job: 20.5 h wall**
  (48.8 Myr/h; smoke over-predicts ~2x). 28,727 steps, 17 Peano overrides, treegrav 58%
  / domain 16% / voronoi 14%.
- End: SFR 0.095 Msun/yr (settled ~0.16 early), 1.26e8 Msun formed (21% of initial
  gas), 536,131 star particles within 5.2 kpc, gas cells 2.37M → 2.68M (early) → 1.94M,
  no runaways.
- **Pending check:** does PartType4 have `StellarFormationTime` without `STELLARAGE`?
  If not, add STELLARAGE to every future Config.sh.
