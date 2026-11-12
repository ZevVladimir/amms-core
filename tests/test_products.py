"""
Pins the product contract in amms.core.products: what goes in comes back, provenance is always
attached, and every refusal (unknown kind, bad qualifier, missing arrays, stray attr, overwrite,
newer schema) actually refuses. Also pins that analysis/ never pulls in h5py (h5py is imported
lazily inside products.py; settled 2026-10-15).

products_root is redirected to tmp_path so nothing touches a real products tree.
"""

import subprocess
import sys

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from amms.core import products


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(products, "products_root", lambda: tmp_path)
    return tmp_path


def newstars(n=4):
    rng = np.random.default_rng(0)
    return {
        "pos_kpc": rng.normal(size=(n, 3)),
        "t_form_gyr": rng.uniform(0, 1, n),
        "mass_msun": np.full(n, 1831.48),
    }


def write(**kw):
    args = {
        "dataset_id": "ext_b12-model2",
        "kind": "newstars",
        "qualifier": "lmc-069",
        "arrays": newstars(),
        "source": "snapshot_069",
        "meta": {"n_ft0_excluded": 3},
    }
    args.update(kw)
    return products.write_product(
        args.pop("dataset_id"), args.pop("kind"), args.pop("qualifier"), args.pop("arrays"), **args
    )


def test_roundtrip(root):
    arrays = newstars()
    path = write(arrays=arrays)
    assert path == root / "ext_b12-model2" / "newstars_lmc-069.h5"

    p = products.read_product(path)
    for k, v in arrays.items():
        np.testing.assert_array_equal(p.arrays[k], v)
    assert p.attrs.dataset_id == "ext_b12-model2"
    assert (p.attrs.kind, p.attrs.qualifier) == ("newstars", "lmc-069")
    assert p.attrs.schema_version == products.SCHEMA_VERSION
    assert p.attrs.meta == {"n_ft0_excluded": 3}
    # Provenance is attached without the caller asking
    assert p.attrs.provenance["source"] == "snapshot_069"
    assert {"created", "script", "code", "amms_core"} <= p.attrs.provenance.keys()


def test_sim_id_dataset_accepted(root):
    path = write(dataset_id="smc_001_edw1_sh03")
    assert path.parent.name == "smc_001_edw1_sh03"


def test_no_temp_file_left_behind(root):
    path = write()
    assert [f.name for f in path.parent.iterdir()] == [path.name]


@pytest.mark.parametrize(
    "kw",
    [
        {"kind": "notakind"},
        {"qualifier": "LMC_069"},
        {"dataset_id": "b12_model2"},  # old spelling, neither SIM_ID nor ext_
    ],
)
def test_write_refuses_bad_attrs(kw):
    with pytest.raises(ValidationError):
        write(**kw)


def test_write_refuses_missing_arrays():
    arrays = newstars()
    del arrays["mass_msun"]
    with pytest.raises(ValueError, match="mass_msun"):
        write(arrays=arrays)


def test_overwrite_refused_unless_asked():
    write()
    with pytest.raises(FileExistsError):
        write()
    write(overwrite=True)


def test_read_refuses_stray_attr():
    path = write()
    with h5py.File(path, "a") as f:
        f.attrs["phyics"] = "hydro"  # the typo extra="forbid" exists to catch
    with pytest.raises(ValidationError):
        products.read_product(path)


def test_read_refuses_newer_schema():
    path = write()
    with h5py.File(path, "a") as f:
        f.attrs["schema_version"] = products.SCHEMA_VERSION + 1
    with pytest.raises(ValueError, match="schema"):
        products.read_product(path)


def test_analysis_does_not_import_h5py():
    # Fresh interpreter: this test process already imported h5py above
    code = (
        "import sys\n"
        "import amms.core.analysis.frames, amms.core.analysis.maps, amms.core.analysis.sanity\n"
        "import amms.core.analysis.sfr\n"
        "print('h5py' in sys.modules)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
