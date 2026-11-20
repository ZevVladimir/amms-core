"""
Write and read cached analysis products: each analysis product is kept to one HDF5 file with provenance attrs

Layout: <products_root>/<dataset_id>/<kind>_<qualifier>.h5
    dataset_id  SimID or ExtID (ids.parse_dataset_id)
    kind        fixed vocabulary defined in KINDS; anything else gets refused
    qualifier   hyphenated slug, e.g. lmc-069 or lmc-069-xy

Release shaped:
    a release copies these files and never converts them
    provenance is only written on creation and can't be backfilled

To keep analysis/ light (numpy + matplotlib) h5py is imported in functions
"""

from __future__ import annotations

import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator

from amms.core.config.paths import products_root
from amms.core.ids import DatasetID, parse_dataset_id
from amms.core.plotting.provenance import record

__all__ = [
    "KINDS",
    "SCHEMA_VERSION",
    "Product",
    "ProductAttrs",
    "product_path",
    "read_product",
    "write_product",
]

SCHEMA_VERSION = 1
QUALIFIER_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_JSON_ATTRS = ("provenance", "meta")  # nested dicts; scalar attrs stay plain so h5ls can show them

# kind -> arrays it must contain
# Units live in the names (canonical kpc, km/s, Msun, Gyr)
KINDS: dict[str, frozenset[str]] = {
    "newstars": frozenset({"pos_kpc", "t_form_gyr", "mass_msun"}),
    "diskstars": frozenset({"pos_kpc", "mass_msun"}),
    "sfrmap": frozenset({"values", "counts", "extent"}),
    "orbit": frozenset({"snapshot", "t_gyr", "pos_kpc", "vel_kms"}),
}


def _json_default(o):
    # default=str turns np.int64(69) into "69". Raise on anything else
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(
        f"{type(o).__name__} in product meta is not JSON-serialisable; convert it first"
    )


class ProductAttrs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str
    kind: str
    qualifier: str
    schema_version: int
    provenance: dict[
        str, Any
    ]  # plotting.provenance.record: source, created, script, code + amms-core git
    meta: dict[str, Any]  # kind-specific context: frame, cuts, counts

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, v: str) -> str:
        parse_dataset_id(v)
        return v

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in KINDS:
            raise ValueError(f"unknown kind {v!r}; add it to products.KINDS first")
        return v

    @field_validator("qualifier")
    @classmethod
    def _qualifier(cls, v: str) -> str:
        if not QUALIFIER_RE.match(v):
            raise ValueError(f"qualifier {v!r} must be lowercase letters/digits joined by hyphens")
        return v


@dataclass(frozen=True)
class Product:
    attrs: ProductAttrs
    arrays: dict[str, np.ndarray]
    path: Path


def product_path(dataset_id: DatasetID | str, kind: str, qualifier: str) -> Path:
    return products_root() / str(dataset_id) / f"{kind}_{qualifier}.h5"


def _check_arrays(kind: str, names) -> None:
    missing = KINDS[kind] - set(names)
    if missing:
        raise ValueError(f"{kind} product is missing arrays {sorted(missing)}")


def write_product(
    dataset_id: DatasetID | str,
    kind: str,
    qualifier: str,
    arrays: dict[str, np.ndarray],
    *,
    source: str,
    meta: dict[str, Any] | None = None,
    repo: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    """
    source: the input data, e.g. the snapshot path
    repo: the repo whose git state to record; default is the calling script's (see provenance.record for how this is done)
    Refuses to overwrite unless asked
    """
    import h5py

    attrs = ProductAttrs(
        dataset_id=str(dataset_id),
        kind=kind,
        qualifier=qualifier,
        schema_version=SCHEMA_VERSION,
        provenance=record(source, Path(repo) if repo else None, None),
        meta=meta or {},
    )

    for name in ("code", "amms_core"):
        if attrs.provenance[name]["dirty"]:
            warnings.warn(
                f"{name} repo has uncommitted changes; product records dirty=True", stacklevel=2
            )

    _check_arrays(kind, arrays)

    path = product_path(attrs.dataset_id, kind, qualifier)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} exists: pass overwrite=True to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)

    # Temp file in the same directory: os.replace across filesystems (/tmp -> /xdisk) raises EXDEV error
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with h5py.File(tmp, "w") as f:
            for k, v in attrs.model_dump().items():
                f.attrs[k] = json.dumps(v, default=_json_default) if k in _JSON_ATTRS else v
            for name, arr in arrays.items():
                f.create_dataset(name, data=np.asarray(arr), compression="gzip")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)  # after successful replace tmp is already gone
    return path


def read_product(path: str | Path) -> Product:
    import h5py

    path = Path(path)
    with h5py.File(path, "r") as f:
        # h5py returns numpy scalars; pydantic requires plain python
        raw = {k: (v.item() if hasattr(v, "item") else v) for k, v in f.attrs.items()}
        arrays = {name: f[name][()] for name in f}
    for k in _JSON_ATTRS:
        raw[k] = json.loads(raw[k])
    attrs = ProductAttrs.model_validate(raw)  # extra="forbid": a stray attribute fails here
    if attrs.schema_version > SCHEMA_VERSION:
        raise ValueError(
            f"{path} has schema {attrs.schema_version}; this amms-core reads <= {SCHEMA_VERSION}"
        )
    _check_arrays(attrs.kind, arrays)
    return Product(attrs, arrays, path)
