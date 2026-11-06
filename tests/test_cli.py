"""
Pins the dispatch contract of amms.core.cli: exit codes, and that a tool's main receives exactly
the arguments after the command name.

Tools are replaced by a fake module in sys.modules (import_module returns it without touching
disk), so no test depends on a real tool or reads real files.
"""

import sys
import types

import pytest

from amms.core import cli


def test_unknown_command_exits_2(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(["not-a-command"])
    assert e.value.code == 2
    assert "usage: amms" in capsys.readouterr().err


def test_no_command_exits_2():
    with pytest.raises(SystemExit) as e:
        cli.main([])
    assert e.value.code == 2


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_exits_0(flag, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([flag])
    assert e.value.code == 0
    assert "check-snap" in capsys.readouterr().err


def test_dispatch_passes_remaining_args(monkeypatch):
    seen = []
    fake = types.ModuleType("amms.core.tools.check_snap")
    fake.main = seen.append
    monkeypatch.setitem(sys.modules, "amms.core.tools.check_snap", fake)

    cli.main(["check-snap", "snap_000.hdf5", "--margin", "5"])
    assert seen == [["snap_000.hdf5", "--margin", "5"]]
