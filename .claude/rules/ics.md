---
paths:
  - "src/amms/core/ics.py"
  - "src/amms/core/codes/makegalaxy.py"
  - "src/amms/core/tools/ic_sanity.py"
  - "tests/test_ic*.py"
  - "tests/test_makegalaxy.py"
---

# ICs — generation routes and known files

Read before touching IC checks, or proposing IC regeneration / grid steps.

## Validated (Puma 2026-11-04)

`ics.py` + `codes/makegalaxy.py` + `amms ic-sanity`: stage-1 dwarf, gridded dwarf and
smc_test pass mass/count/hash. Ethan's double-shifted file FAILs `mass_type0` at
16.25%; its sha256 `3909e986…` confirms the top-level `dbl_shift_*` rename was the
broken file. `.parameters` is `%g` (6 sig. digits, ~5e-6 rel) → `MASS_RTOL = 1e-5`.

## Registered files

- `edw1` = gridded Ethan dwarf (`efcaf95e…`). Stage-1 `ics_dwarf_live_1e6.hdf5`
  sha256 `617facab35305df8b516dfbc26b50b632a44278f2c35ad4fe7d8a31b7a327f47` —
  **reuse it, never regenerate just to fix the grid** (grid step ~2 min).
- `smct1` = `/groups/gbesla/zvladimir/ics/smc_test/ics_smc.hdf5`, sha256
  `ba288d154e51774b106e296d44504eae7da263b6e84339cf5fdd4ab701930a6b`.
  `NumPart_Total=[522000 gas, 500000 dm, 1044000 disk, 0, 0, 1 BH]`, `HubbleParam=1`,
  `BoxSize=0` (ignored; gas still must be shifted into the box), no bulge. PartType0/2
  carry `Metallicity`; PartType2 carries `StellarFormationTime`
  (`DiskPopMode=exponential`). float32 → no `INPUT_IN_DOUBLEPRECISION`. Units kpc /
  1e10 Msun / km/s, inferred from the mass budget (halo 1.796 vs `M200=1.84741`), not
  from an explicit generator note.

## Two routes, both MakeNewDisk (Springel+05 Hernquist halo + exp disk), different binaries

- **Ethan's dwarf:** `MakeGalaxy_new` (Himansh, `/groups/ejahn/.../MyMakeGalaxy`); the
  `makegalaxy` checkout matches it (assert string `ZSIZE-1`). Stage 2:
  `arepo_grid/Arepo_grid` (`ADDBACKGROUNDGRID=32`, `SHIFT_BY_HALF_BOX`, BoxSize 200).
- **smc_test:** `MakeGalaxy_puma9_modified_bulge` (Himansh,
  `/home/u19/himansh/makegalaxy_puma9`). **Source not on disk** (hardcodes ZSIZE=512),
  no generator log — provenance gap.
- `bin_hdf_conv.py` produced neither (both wrote HDF5 directly). The garbled-name dwarf
  duplicate is byte-identical (`makegalaxy:main.c` unterminated `strncpy`, harmless).

## Box / grid facts

- **AREPO terminates if any gas cell is outside `[0, BoxSize]` under
  `GRAVITY_NOT_PERIODIC`** (`arepo-smuggle:src/main/init.cc:2642-2657`). Origin-centred
  gas needs a shift and probably a background grid.
- **The gridded dwarf from Ethan was shifted twice** (+100 `SHIFT_BY_HALF_BOX` in
  `arepo-grid:src/init.c`, +100 by the grid's own shift) → galaxy at (200,200,200), gas
  5.97e8 → 9.69e7 Msun (84% lost), Metallicity/StellarFormationTime dropped. New cells
  only for empty leaves inside (0,BoxSize)^3
  (`arepo-grid:src/add_backgroundgrid/add_bggrid.c:87-89`); an old particle with no new
  cell in its Hsml deposits nothing, silently. Second shift fires because `xmin<0` for
  *any* particle (`arepo-grid:src/add_backgroundgrid/add_bggrid.c:421`). Same logic in
  arepo-smuggle (`arepo-smuggle:src/main/init.cc:2620`,
  `arepo-smuggle:src/add_backgroundgrid/add_bggrid.cc:420,471`). `SHIFT_BY_HALF_BOX` runs
  in `init()`, i.e. every start except restart files
  (`arepo-smuggle:src/main/main.cc:452`) — re-shifts on restart-from-snapshot.
- **Can't just drop `SHIFT_BY_HALF_BOX`:** the gas-in-box check follows it
  (`arepo-grid:src/init.c:2968-2984`), before the grid's auto-shift (tried 2026-10-16).
  Fix used: keep it in the grid build, patch `add_bggrid.c:421` to test `xmin_gas_glob`.
  Production build must not set it (IC already in box coords).
- **Collisionless particles outside the box are safe** (audited 2026-10-16): grid run
  builds domain from gas + box, gravity tree from gas; halo/stars written back
  unchanged. `do_box_wrapping` skips non-gas under GRAVITY_NOT_PERIODIC. Real limit: the
  *gas* mesh is periodic even with non-periodic gravity — keep outflows inside BoxSize.
  Diff the logged gas mass before/after remap; the printed `ReferenceGasPartMass`
  inherits any loss.
- Grid-step Puma constraints: NTask <= `min_topleave_num` (61 for BoxSize 200);
  `MaxMemSize` must fit memory/task (9000 with `cpus-per-task=2` worked). Output lands
  at `<InitCondFile>-with-grid`, beside the input (`arepo-grid:src/io.c:796`).

## Generator facts

- **MakeGalaxy's 41 h is ~40 h in velocity sampling.** `set_halo_velocities`
  (`makegalaxy:haloset.c:154-162`, same `makegalaxy:bulgeset.c:118-126`) recomputes
  `comp_phi` on every rejection at a fixed position; hoisting it is exact (`srand48(666)`,
  no global writes). Makefile also has `OPTIMIZE = -g` (-O0).
- smc_test `FactorForSofterEQS=1`: vertical structure solved with SH03 eff. EOS
  (`makegalaxy:effmodel.c:166`) but `u` written flat 1e4 K and SMUGGLE has no eff. EOS →
  expect vertical collapse at t=0. Dwarf used 0, consistent. `U4MOD` off.
- **`.vc` file** (`makegalaxy:main.c:129-149`): written to the **cwd**, not OutputDir
  (OutputDir join commented out), as `<OutputFile minus .hdf5>.vc`. Layout: param header
  ending `done` (`main.c:217`); `POINTS`=1000; R grid (R200/1000 · i); then **v_c² (not
  v_c)** for total, disk, halo, bulge (`makegalaxy:toomre.c:97+`); then Toomre count + R
  (≤ 6H) + Q stars + Q gas (`toomre.c:42`, GB gas-modified; Makefile builds `toomre.o`,
  not `toomre_orig`). Laptop has only the example `ics_mw.vc`. Puma: `smct1` →
  `/groups/gbesla/zvladimir/ics/smc_test/ics_smc.vc`. edw1 candidate is a file named
  just `.vc` in `/groups/.../make_ics_from_ethan/MakeGalaxy/` — the garbled OutputFile
  fails `strstr(".hdf5")`, so buf stays empty; **unverified that it is the dwarf's**
  (header-vs-`.parameters` diff pending; any later run from that cwd overwrites it).
- smc_test `Zmet0=0.032` is the MW template (~2x solar), not SMC.
- Open regeneration decisions: Zmet0, FactorForSofterEQS, halo truncation, V200's
  assumed h (ask Ethan for his dwarf too).
