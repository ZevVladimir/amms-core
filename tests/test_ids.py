"""
Pins the SIM_ID grammar <project>_<NNN>_<ic>_<slug>: one canonical spelling per identity, the
IC tag's shape (letters then a version number), direct construction held to the same rules as
parse(), and the run counter shared by all ICs within a project.
"""

import pytest

from amms.core.ids import InvalidSimID, SimID, create_run_dir, existing_ids, slugify


@pytest.mark.parametrize(
    "text", ["smc_001_edw1_sh03", "mwsat_142_edw2_agn-on-lowres", "m2_001_a1_a"]
)
def test_roundtrip(text):
    assert str(SimID.parse(text)) == text


def test_fields():
    sid = SimID.parse("smc_001_edw1_sh03")
    assert (sid.project, sid.number, sid.ic, sid.slug) == ("smc", 1, "edw1", "sh03")


@pytest.mark.parametrize(
    "text",
    [
        "mwsat_7_edw1_fiducial",  # not zero-padded
        "mwsat_0007_edw1_fiducial",  # non-canonical padding
        "MWSat_007_edw1_fiducial",  # uppercase project
        "mw_sat_007_edw1_fiducial",  # underscore in project
        "mwsat_007_edw1_Fiducial",  # uppercase slug
        "mwsat_007_edw1_fid_ucial",  # underscore in slug
        "mwsat_007_edw1_",  # empty slug
        "mwsat_007_edw1",  # missing slug
        "smc_001_sh03",  # missing IC (the old 3-field form)
        "smc_001_edw_sh03",  # IC without a version number
        "smc_001_EDW1_sh03",  # uppercase IC
        "smc_001_edw-1_sh03",  # hyphen in IC
        "smc_001_1edw_sh03",  # IC starting with a digit
        # NOT here: "smc_001_sh03_edw1" (IC and slug swapped) is grammatically valid, since
        # "sh03" is tag-shaped. Only the registry catches it: check_ic_tag("sh03") FAILs
    ],
)
def test_rejects_noncanonical(text):
    assert not SimID.is_valid(text)
    with pytest.raises(InvalidSimID):
        SimID.parse(text)


@pytest.mark.parametrize(
    "fields",
    [
        ("smc", 1, "Bad", "x"),  # IC not tag-shaped
        ("smc", 1, "edw1", "Bad Slug"),  # slug not canonical
        ("Smc", 1, "edw1", "x"),  # project not canonical
    ],
)
def test_direct_construction_held_to_grammar(fields):
    with pytest.raises(InvalidSimID):
        SimID(*fields)


def test_with_slug_keeps_project_number_ic():
    sid = SimID.parse("smc_001_edw1_sh03").with_slug("SMUGGLE fiducial")
    assert str(sid) == "smc_001_edw1_smuggle-fiducial"
    with pytest.raises(ValueError):
        sid.with_slug("!!!")  # cannot be slugified


def test_slugify():
    assert slugify("Fiducial Run (high res)") == "fiducial-run-high-res"


def test_counter_is_per_project_across_ics(tmp_path):
    a, _ = create_run_dir(tmp_path, "smc", "edw1", "sh03")
    b, _ = create_run_dir(tmp_path, "smc", "smct1", "Another Run")
    c, _ = create_run_dir(tmp_path, "lmc", "lmct1", "first")
    assert (str(a), str(b), str(c)) == (
        "smc_001_edw1_sh03",
        "smc_002_smct1_another-run",  # a new IC does not restart the count
        "lmc_001_lmct1_first",  # another project does
    )


def test_allocation_skips_numbers_taken_by_any_ic(tmp_path):
    (tmp_path / "smc_005_edw1_manual").mkdir()
    sid, _ = create_run_dir(tmp_path, "smc", "smct1", "next")
    assert sid.number == 6


def test_existing_ids_ignores_junk(tmp_path):
    (tmp_path / "smc_001_edw1_ok").mkdir()
    (tmp_path / "smc_002_old-form").mkdir()  # 3-field name: not a SIM_ID any more
    (tmp_path / "scratch-notes").mkdir()
    (tmp_path / "smc_001_edw1_ok.tar").touch()
    assert [str(s) for s in existing_ids(tmp_path)] == ["smc_001_edw1_ok"]
