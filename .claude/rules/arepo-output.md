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
- **run-summary scope (user, 2026-11-13):** ONE tool, sections: disk footprint (stat
  only: per-snap, output/, restartfiles/, projection to TimeMax), completion/restarts
  (`end` sentinel), mass conservation, timebins/energy, memory high-water. Stdout
  Markdown + `savefig` figures under `$AMMS_PRODUCTS/<sim_id>/figures/` (no summary
  product/schema). `--no-snap` skips particle reads. Parsers → `codes/arepo.py`, checks →
  `analysis/sanity.py`.
- Mass check: judge M_stars vs `cumsum(sfr col 5)`; gas+stars vs initial reported, not
  judged (user, 2026-11-13). Initial gas from t=0, plus a written IC-vs-t=0 confirmation
  row. `GFM_InitialMass` needs `GFM_STELLAR_EVOLUTION` + `GFM_OUTPUT_MASK & 4`
  (`arepo-smuggle:src/io/snap_io.cc:347-349`); run #1 Config.sh has no GFM at all.
- Evolution plots: default fixed time set, overridable (user, 2026-11-13).

## Log formats (run #1 output 2026-11-13 + upstream printf)

- **energy.txt**: 30 `%g` cols (`arepo-smuggle:src/logs/global.cc:91`): 0 time, 1-3
  Eint/Epot/Ekin, 4-21 per-type (int,pot,kin)×6, **22-27 per-type mass**, 28 EgyInjection,
  29 EnergyMag. Every TimeBetStatistics (~10 Myr). **Epot = 0 everywhere: no
  EVALPOTENTIAL** (`global.cc:267`) → no energy-conservation check possible.
- **Run #1 mass from energy.txt:** gas 0.0604452 → 0.0478371, stars 0 → 0.0126081; sum
  = initial to all 6 printed digits. M_stars(end) ≈ sfr.txt formed 1.26e8 → no stellar
  mass return in this config; current mass = formed mass here. No snapshot read needed.
- **timebins.txt**: block per sync point; header `Sync-Point %d, Time: %.10g, Systemstep:
  %g` (`logs.cc:549`). Bin-line columns are Config-dependent: extra count cols for
  `SMUGGLE_STAR_FEEDBACK_LIMIT_GAS_TIMESTEP`, `TRACER_PARTICLE`, `DUST_LIVE`
  (`logs.cc:600-690`) → locate columns from the `Occupied timebins:` header, never
  fixed positions. Leading `X` = synchronized. Run #1: min bin 11 at step 1 (5 cells),
  14 at end; max bin 20 (dt 0.002).
- **memory.txt**: block when either max-task high-water grows ≥5%
  (`arepo-smuggle:src/data/mymalloc.cc:411,422`) → last line is the peak to within 5%.
  **Use `Without Generic`, never `Largest Allocation`:** generic comm buffers grab 30% of
  free memory (`arepo-smuggle:src/mpi_utils/generic_comm_helpers2.h:68`), so the total
  tracks MaxMemSize by construction. Run #1: 4495.58 of MaxMemSize 4500 (meaningless);
  without generic **585.6 MB = 13%** of MaxMemSize.
- **hostmemory.txt**: only Sync-Point 0 in run #1 (1 block, 94 ranks + prterun/slurm
  rows) → no high-water information; not parsed.
- Run #1 disk: 11 snapshots (100 Myr cadence), ~0.97 GB each (~10.6 GB);
  `restartfiles/` 19 GB = 188 files = `restart.N` + `bak-restart.N` for 94 tasks (one
  set ≈ 9.5 GB ≈ 10× a snapshot; fixed, not per-snapshot); logs 212 MB (cpu.txt 122 MB);
  `output/` 30 GB. `du -sh A A/sub` prints one line (du skips already-counted dirs).
- Python on Puma: a venv only works under its own interpreter's module. `amms` = 3.11.4
  (`source env/activate.sh`), `legacy-gadget` = 3.14.2. Loading the other module swaps
  it out (`libpython3.x.so` not found). **Propose commands for whichever venv the user's
  prompt shows; never a bare `module load python/...`.** No `h5ls` in either.

## First run: `smc_001_edw1_sh03`

run-summary 2026-11-17: all PASS except **`t0_mass_gas` FAIL, energy.txt t=0 gas 1.33%
above the IC** (0.0604452 vs ~0.05965 = the 5.97e8 budget; collisionless types agree to
~1e-6). **Confirmed 2026-11-17: `MinimumDensityOnStartUp` 1e-10** raises cells below it and
rescales their mass (`arepo-smuggle:src/main/init.cc:1419-1424`). IC gas 0.0596514 →
snap_000 0.0604452 (+7.94e-4 = 7.9e6 Msun), same N (2,374,442); 5001 cells at the floor
carrying 8.50e-4. Floor gas is background, not galaxy; "fraction of initial gas formed"
must use IC gas or a galaxy region. **Open:** floor cells' m/ρ = 8.5e6 kpc³ > box 8e6 kpc³
— snapshot Density may not be m/V of the t=0 mesh. Peano overrides: 17 in the production
log; smoke logs add 1 + 4 → pass only the production `.out` (+ its restarts) to `--log`.

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
- **No stellar ages in run #1 (confirmed 2026-11-17):** PartType4 = Coordinates, Masses,
  ParticleIDs, Velocities only. Birth time is not even stored in memory without
  `STELLARAGE` (`arepo-smuggle:src/cooling_sfr/starformation.cc:721-723`,
  `arepo-smuggle:src/data/allvars.h:3031`) → unrecoverable. Run #1 SFH: global from
  sfr.txt; spatial only by new-ID first appearance (birth bracketed to the 100 Myr snapshot
  cadence). **Add `STELLARAGE` to every future Config.sh** (consider `EVALPOTENTIAL` too:
  energy check + potential centring).
