"""
Sets the identifier for each simulation that is used for directories, figures, notes, etc

Current form: <project>_<NNN>_<ic>_<slug>
- Project: the name of the project with lowercase letters and numbers (starts with a letter). No underscores
- NNN: a three digit zero-padded number unique to each simulation within the project
- ic: letters then a version number of the ICs used for the simulation
- slug: a short description of the simulation joined with hyphens

Use underscores to separate the fields and the hyphens are kept for the slug
Creates a consistent expectation from .split("_") and .split("-") for the fields of the identifier
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

NUMBER_WIDTH = 3

IC_TAG = r"[a-z]+[0-9]+"  # letters then a version number: edw1, smct2. Shared with ics.py
IC_TAG_RE = re.compile(rf"^{IC_TAG}$")

SIM_ID_RE = re.compile(
    r"^(?P<project>[a-z][a-z0-9]{1,15})"
    r"_(?P<number>\d{3,})"
    rf"_(?P<ic>{IC_TAG})"
    r"_(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)


class InvalidSimID(ValueError):
    """Raised when a string is not a valid simulation identifier."""


@dataclass(frozen=True, order=True)
class SimID:
    """Simulation identifier that is immutable and sortable"""

    project: str
    number: int  # per project, across ICs: unique within the project on its own
    ic: str  # versioned IC tag; check existence and sha256 using amms.core.ics.check_ic_tag
    slug: str

    def __post_init__(self) -> None:
        # Direct construction (create_run_dir, with_slug) must not be able to build an ID that
        # parse() would reject. Only have one valid spelling per identity regardless of how the object was made
        if not SIM_ID_RE.match(str(self)):
            raise InvalidSimID(f"{str(self)!r} is not a valid SIM_ID")

    def __str__(self) -> str:
        return f"{self.project}_{self.number:0{NUMBER_WIDTH}}_{self.ic}_{self.slug}"

    @classmethod
    def parse(cls, text: str) -> SimID:
        """Turns a string into a SimID object"""
        m = SIM_ID_RE.match(text)
        if m:
            sid = cls(m["project"], int(m["number"]), m["ic"], m["slug"])
            # Guarantees only one spelling per identity
            if str(sid) == text:
                return sid
        raise InvalidSimID(
            f"{text!r} is not a canonical SIM_ID.\n"
            "Expected format: <project>_<NNN>_<ic>_<slug>\n"
            "  - project: lowercase letters and numbers, starts with a letter, no underscores\n"
            "  - NNN: three digit zero-padded number\n"
            "  - ic: versioned IC tag, lowercase letters then digits (e.g. edw1)\n"
            "  - slug: lowercase letters and numbers joined with hyphens"
        )

    @classmethod
    def is_valid(cls, text: str) -> bool:
        """Checks if a string is a valid simulation identifier"""
        try:
            cls.parse(text)
        except InvalidSimID:
            return False

        return True

    def with_slug(self, slug: str) -> SimID:
        """Returns a new SimID with the same project and number and IC but a new description slug"""
        return SimID(self.project, self.number, self.ic, slugify(slug))


def slugify(text: str) -> str:
    """Converts a string into a slug valid for SimID"""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not s:
        raise ValueError(f"Cannot slugify {text!r} into a valid slug")
    return s


def existing_ids(root: Path, project: str | None = None) -> list[SimID]:
    """Returns all the valid SIM_ID appearing as directories in the root path"""
    if not root.is_dir():
        return []
    found = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            sid = SimID.parse(entry.name)
        except InvalidSimID:
            continue  # Unrelated directory name can safely skip

        if project is None or sid.project == project:
            found.append(sid)

    return sorted(found)


def create_run_dir(
    root: Path, project: str, ic: str, slug: str, *, attempts: int = 20
) -> tuple[SimID, Path]:
    """
    Allocate the next run number for the current project and create its directory.
    Numbers are counted per project across all ICs. NNN alone identifies a run within a project
    """
    slug = slugify(slug)
    for _ in range(attempts):
        used = {sid.number for sid in existing_ids(root, project)}
        sid = SimID(project, max(used, default=0) + 1, ic, slug)
        try:
            (run_dir := root / str(sid)).mkdir(parents=True)
        except FileExistsError:
            continue

        return sid, run_dir
    raise RuntimeError(f"could not allocate a run number under {root} after {attempts} attempts")
