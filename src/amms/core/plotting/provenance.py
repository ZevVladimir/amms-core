"""
Figure stamping: every saved fiugres carries what data it shows and what code drew it

Always use this savefig not the plt.savefig to ensure consistency and guarantee knowledge of where every plot comes from
Embed the record in the file's metadata

Only PNG, PDF, SVG
read_provenance reads PNG SVG
for PDF use `strings fig.pdf | grep '"source"'`
Git state comes from the `git` CLI if outside repo/no git set to None rather than error
"""

from __future__ import annotations

import json
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

__all__ = ["read_provenance", "savefig"]
_METADATA_KEY = {".png": "Description", ".pdf": "Subject", ".svg": "Description"}


def _git_state(where: Path) -> dict[str, Any]:
    """Commit and dirty flag of the repo containing `where`. Untracked files dont' count"""

    def git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", str(where), *args], capture_output=True, text=True, check=True
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return out.stdout.strip()

    top = git("rev-parse", "--show-toplevel")
    if top is None:
        return {"repo": None, "commit": None, "dirty": None}
    status = git("status", "--porcelain", "--untracked-files=no")
    return {"repo": top, "commit": git("rev-parse", "HEAD"), "dirty": bool(status)}


def _calling_script() -> Path | None:
    main = sys.modules.get("__main__")
    f = getattr(main, "__file__", None)  # notebooks and REPL have no __file__
    return Path(f).resolve() if f else None


def _record(source: str, repo: Path | None, extra: dict | None) -> dict[str, Any]:
    script = _calling_script()
    code_dir = repo or (script.parent if script else Path.cwd())
    try:
        version = metadata.version("amms-core")
    except metadata.PackageNotFoundError:
        version = None
    return {
        "source": source,
        "created": datetime.now(timezone.utc).isoformat(),
        "script": str(script) if script else "<interactive>",
        "code": _git_state(code_dir),
        "amms_core": {"version": version, **_git_state(Path(__file__).parent)},
        "extra": extra or {},
    }


def _short(state: dict[str, Any]) -> str:
    if not state["commit"]:
        return "?"
    return state["commit"][:7] + ("*" if state["dirty"] else "")


def savefig(
    fig,
    path: str | Path,
    *,
    source: any,
    repo: str | Path | None = None,
    extra: dict | None = None,
    stamp: bool = True,
    **kwargs,
) -> Path:
    """
    Save `fig` with an embedded provenance record

    source: What the figure shows: a SimID (str() is used), an IC id, or a dataset name
    repo:   repo whose state to record; default: the one containing the calling script
    extra:  JSON-serialisable context, e.g. the input product's metadata
    stamp:  draw the short corner label; embedded record is still written no matter what
    kwargs: passed to Figure.savefig (dpi, bbox_inches,...)
    """
    path = Path(path)
    key = _METADATA_KEY.get(path.suffix.lower())
    if key is None:
        raise ValueError(f"{path.suffix!r} not supported; use one of {sorted(_METADATA_KEY)}")

    rec = _record(str(source), Path(repo) if repo else None, extra)
    for name in ("code", "amms_core"):
        if rec[name]["dirty"]:
            warnings.warn(f"{name} repo has uncommitted changes; figure records '*'", stacklevel=2)

    label = None
    if stamp:
        repo_name = Path(rec["code"]["repo"]).name if rec["code"]["repo"] else "?"
        text = f"{rec['source']} | {repo_name}@{_short(rec['code'])} | amms-core@{_short(rec['amms_core'])}"
        label = fig.text(0.995, 0.005, text, ha="right", va="bottom", fontsize=5, color="0.5")

    try:
        md = {**kwargs.pop("metadata", {}), key: json.dumps(rec, default=str)}
        fig.savefig(path, metadata=md, **kwargs)
    finally:
        if label is not None:
            label.remove()  # leave Figure as caller built it
    return path


def read_provenance(path: str | Path) -> dict[str, Any]:
    """
    Recover the record from a PNG or SVG written by savefig
    """
    path = Path(path)
    if path.suffix.lower() == ".png":
        from PIL import Image

        with Image.open(path) as im:
            return json.loads(im.text["Description"])
    if path.suffix.lower() == ".svg":
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        node = ET.parse(path).getroot().find(".//dc:description", ns)
        return json.loads(node.text)
    raise ValueError(f"reading {path.suffix!r} not supported; see module docstring for PDFs")
