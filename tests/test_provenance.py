"""
Pins figure provenance (invariant 6): the record survives inside the saved file, the corner
label does not leak into the caller's Figure, unsupported formats are refused, and missing git
degrades to None instead of crashing.
"""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
from PIL import Image

from amms.core.plotting.provenance import read_provenance, savefig

RECORD_KEYS = {"source", "created", "script", "code", "amms_core", "extra"}

# The working tree is often dirty while developing; the warning is intended, not a failure
pytestmark = pytest.mark.filterwarnings("ignore:.*uncommitted changes")


@pytest.fixture
def fig():
    f, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    yield f
    plt.close(f)


@pytest.mark.parametrize("ext", [".png", ".svg"])
def test_record_roundtrips(fig, tmp_path, ext):
    out = savefig(fig, tmp_path / f"f{ext}", source="ic:test@abc123", extra={"snap": 10})
    rec = read_provenance(out)
    assert set(rec) == RECORD_KEYS
    assert rec["source"] == "ic:test@abc123"
    assert rec["extra"] == {"snap": 10}
    assert set(rec["code"]) == {"repo", "commit", "dirty"}
    assert {"version", "repo", "commit", "dirty"} <= set(rec["amms_core"])


def test_stamp_does_not_leak_into_figure(fig, tmp_path):
    n = len(fig.texts)
    savefig(fig, tmp_path / "f.png", source="x", stamp=True)
    assert len(fig.texts) == n  # label drawn for the save only


def test_unsupported_format_refused(fig, tmp_path):
    with pytest.raises(ValueError):
        savefig(fig, tmp_path / "f.jpg", source="x")


def test_outside_git_degrades_to_none(fig, tmp_path):
    rec = read_provenance(savefig(fig, tmp_path / "f.png", source="x", repo=tmp_path))
    assert rec["code"] == {"repo": None, "commit": None, "dirty": None}


def test_caller_metadata_kept(fig, tmp_path):
    out = savefig(fig, tmp_path / "f.png", source="x", metadata={"Title": "my title"})
    with Image.open(out) as im:
        assert im.text["Title"] == "my title"
        assert "Description" in im.text  # the record is still there alongside
