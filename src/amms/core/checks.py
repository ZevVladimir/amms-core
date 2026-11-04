"""
Have a singular, standardized result type that is used for all sanity checks:
    ICs
    gridded ICs
    pre-submmit
    snapshots
    logs
Invariant chceks return PASS/WARN/FAIL on their own

Diagnoistics (profiles/maps) are figures for a human to judge and do not produce the CheckResults type
Only use Stdlib so that it can be run without dependencies
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

__all__ = ["CheckResult", "Status", "worst"]


class Status(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    value: Any = None
    expected: Any = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


def worst(results: Iterable[CheckResult]) -> Status:
    """
    Returns the most sever status allowing for a one word summary
    """
    order = [Status.PASS, Status.WARN, Status.FAIL]
    return max((r.status for r in results), key=order.index, default=Status.PASS)
