"""
Pins the IC tag registry (ics/ic_tags.yaml): one tag = one file by sha256, tags never reused,
re-registering is idempotent, and check_ic_tag fails a run whose IC is not the tagged file.
"""

import h5py
import numpy as np
import pytest

from amms.core.checks import Status
from amms.core.ics import check_ic_tag, read_tags, register_tag


def make_ic(path, seed):
    """Minimal IC file; the seed makes the content (and so the sha256) distinct"""
    with h5py.File(path, "w") as f:
        f.create_group("Header")
        f.create_dataset("PartType1/Coordinates", data=np.full((2, 3), seed, np.float32))
    return path


@pytest.fixture
def setup(tmp_path):
    reg = tmp_path / "ic_tags.yaml"
    a = make_ic(tmp_path / "a.hdf5", 1.0)
    b = make_ic(tmp_path / "b.hdf5", 2.0)
    return reg, a, b


def test_register_and_read_back(setup):
    reg, a, _ = setup
    entry = register_tag(reg, "edw1", a)
    tags = read_tags(reg)
    assert set(tags) == {"edw1"}
    assert tags["edw1"].sha256 == entry.sha256
    assert reg.read_text().startswith("# ")  # machine-written header present


def test_reregister_same_file_is_noop(setup):
    reg, a, _ = setup
    first = register_tag(reg, "edw1", a)
    assert register_tag(reg, "edw1", a) == first
    assert set(read_tags(reg)) == {"edw1"}


def test_tag_never_reused_for_another_file(setup):
    reg, a, b = setup
    register_tag(reg, "edw1", a)
    with pytest.raises(ValueError):
        register_tag(reg, "edw1", b)


def test_file_gets_only_one_tag(setup):
    reg, a, _ = setup
    register_tag(reg, "edw1", a)
    with pytest.raises(ValueError):
        register_tag(reg, "edw2", a)


@pytest.mark.parametrize("bad", ["edw", "EDW1", "edw-1", "1edw", "edw_1", ""])
def test_bad_tag_shape_rejected(setup, bad):
    reg, a, _ = setup
    with pytest.raises(ValueError):
        register_tag(reg, bad, a)
    assert not reg.exists()  # nothing written on refusal


def test_missing_registry_reads_empty(tmp_path):
    assert read_tags(tmp_path / "nope.yaml") == {}


def test_check_ic_tag(setup):
    reg, a, b = setup
    register_tag(reg, "edw1", a)
    assert check_ic_tag("edw1", a, reg).status is Status.PASS
    assert check_ic_tag("smct1", a, reg).status is Status.FAIL  # unregistered tag
    wrong = check_ic_tag("edw1", b, reg)  # the run holds a different file
    assert wrong.status is Status.FAIL
    assert wrong.value != wrong.expected
