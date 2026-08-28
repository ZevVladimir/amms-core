import pytest

from amms.core.ids import InvalidSimID, SimID, create_run_dir, existing_ids, slugify


@pytest.mark.parametrize("text", ["mwsat_007_fiducial", "mwsat_142_agn-on-lowres", "m2_001_a"])
def test_roundtrip(text):
    assert str(SimID.parse(text)) == text


@pytest.mark.parametrize(
    "text",
    [
        "mwsat_7_fiducial",  # not zero-padded
        "mwsat_0007_fiducial",  # non-canonical padding
        "MWSat_007_fiducial",  # uppercase
        "mw_sat_007_fiducial",  # underscore in project
        "mwsat_007_Fiducial",  # uppercase slug
        "mwsat_007_fid_ucial",  # underscore in slug
        "mwsat_007_",  # empty slug
        "mwsat_007",  # missing slug
    ],
)
def test_rejects_noncanonical(text):
    assert not SimID.is_valid(text)
    with pytest.raises(InvalidSimID):
        SimID.parse(text)


def test_slugify():
    assert slugify("Fiducial Run (high res)") == "fiducial-run-high-res"


def test_allocation_increments_and_ignore_other_projects(tmp_path):
    a, _ = create_run_dir(tmp_path, "mwsat", "fiducial")
    b, _ = create_run_dir(tmp_path, "mwsat", "Another Run")
    c, _ = create_run_dir(tmp_path, "other", "first")

    assert (str(a), str(b), str(c)) == (
        "mwsat_001_fiducial",
        "mwsat_002_another-run",
        "other_001_first",
    )


def test_allocation_skips_numbers_taken_by_a_different_slug(tmp_path):
    (tmp_path / "mwsat_005_manual").mkdir()
    sid, _ = create_run_dir(tmp_path, "mwsat", "next")
    assert sid.number == 6


def test_existing_ids_ignores_junk(tmp_path):
    (tmp_path / "mwsat_001_ok").mkdir()
    (tmp_path / "scratch-notes").mkdir()
    (tmp_path / "mwsat_001_ok.tar").touch()
    assert [str(s) for s in existing_ids(tmp_path)] == ["mwsat_001_ok"]
