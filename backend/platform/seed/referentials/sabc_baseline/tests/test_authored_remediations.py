"""Tests for the authored per-control remediations baked into the seed.

Every authored cell must survive the platform's guidance extraction VERBATIM
(that is the whole point — hand-written scripts, no heuristics) and every
script must be syntactically valid bash. A cell that fails either check would
silently regress a control at the next seed regeneration.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from authored_remediations import REMEDIATIONS  # noqa: E402

# The platform's extractor — authored cells must round-trip through it.
_BACKEND_SRC = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "..", "src"))
sys.path.insert(0, _BACKEND_SRC)
from modules.profiles.artifact_generator import extract_shell  # noqa: E402

_ALLOWED_FIELDS = {
    "validate_debian", "configure_debian", "validate_redhat", "configure_redhat",
}

_ALL_CELLS = [
    (cid, field, text)
    for cid, fields in sorted(REMEDIATIONS.items())
    for field, text in sorted(fields.items())
]


def _script_of(cell: str) -> str:
    m = re.search(r"```bash\n(.*?)```", cell, re.S)
    assert m, "cell has no fenced bash block"
    return m.group(1)


class TestStructure:
    def test_only_known_fields(self) -> None:
        for cid, fields in REMEDIATIONS.items():
            unknown = set(fields) - _ALLOWED_FIELDS
            assert not unknown, f"{cid}: unknown fields {unknown}"

    @pytest.mark.parametrize("cid,field,cell", _ALL_CELLS,
                             ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS])
    def test_script_starts_with_bash_shebang(self, cid, field, cell) -> None:
        # The shebang routes the block through extract_shell's verbatim path —
        # without it, comment lines would be mis-read as prompt commands.
        assert _script_of(cell).startswith("#!/bin/bash\n"), f"{cid}/{field}"

    @pytest.mark.parametrize("cid,field,cell", _ALL_CELLS,
                             ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS])
    def test_no_sabc_marker_lines_inside_scripts(self, cid, field, cell) -> None:
        # extract_shell strips '# [SABC]'-prefixed lines anywhere in the cell;
        # inside a script that would silently delete code.
        assert "# [SABC]" not in _script_of(cell), f"{cid}/{field}"

    @pytest.mark.parametrize("cid,field,cell", _ALL_CELLS,
                             ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS])
    def test_no_heredoc_terminator_collision(self, cid, field, cell) -> None:
        # Validate scripts are embedded in a <<-'SABC_V' Ruby heredoc.
        assert "SABC_V" not in cell, f"{cid}/{field}"


class TestRoundTrip:
    @pytest.mark.parametrize("cid,field,cell", _ALL_CELLS,
                             ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS])
    def test_extract_shell_keeps_script_verbatim(self, cid, field, cell) -> None:
        script = _script_of(cell).rstrip("\n")
        assert extract_shell(cell) == script, (
            f"{cid}/{field}: extract_shell altered the authored script"
        )

    @pytest.mark.parametrize("cid,field,cell", _ALL_CELLS,
                             ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS])
    def test_script_is_valid_bash(self, cid, field, cell) -> None:
        proc = subprocess.run(
            ["bash", "-n"], input=_script_of(cell),
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"{cid}/{field}: {proc.stderr.strip()}"


class TestSemantics:
    @pytest.mark.parametrize(
        "cid,field,cell",
        [t for t in _ALL_CELLS if t[1].startswith("validate")],
        ids=[f"{c}/{f}" for c, f, _ in _ALL_CELLS if f.startswith("validate")])
    def test_validates_declare_explicit_exits(self, cid, field, cell) -> None:
        # Every authored validate states its verdict explicitly — no falling
        # off the end with whatever the last grep happened to return.
        assert re.search(r"\bexit \$?\w+", _script_of(cell)), f"{cid}/{field}"

    def test_na_guards_use_101_only_in_validates(self) -> None:
        for cid, field, cell in _ALL_CELLS:
            if field.startswith("configure"):
                assert "exit 101" not in cell, (
                    f"{cid}/{field}: configure must exit 0 when not applicable"
                )

    def test_sudoers_edits_are_visudo_checked(self) -> None:
        for cid, field, cell in _ALL_CELLS:
            if not field.startswith("configure"):
                continue
            s = _script_of(cell)
            if "/etc/sudoers" in s and (">>" in s or "sed -ri" in s):
                assert "visudo -cf" in s, f"{cid}/{field}: unchecked sudoers edit"

    def test_sshd_edits_are_sshd_t_checked(self) -> None:
        for cid, field, cell in _ALL_CELLS:
            if not field.startswith("configure"):
                continue
            s = _script_of(cell)
            if "sshd_config" in s and ">" in s:
                assert "sshd -t" in s, f"{cid}/{field}: unchecked sshd edit"
