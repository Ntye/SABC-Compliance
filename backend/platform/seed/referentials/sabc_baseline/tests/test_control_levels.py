"""The CIS level map is what makes Non-critical (L1) and Critical (L1+L2) real.

Verifies the curated Level-2 set is internally consistent, references only real
controls, and lands correctly in the committed seed CSV.
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from control_levels import CIS_LEVEL_2, level_for  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(os.path.dirname(HERE), "sabc_baseline.csv")


def _controls() -> dict[str, str]:
    with open(CSV_PATH, encoding="utf-8") as fh:
        return {r["Control ID"]: (r["CIS Level"] or "").strip()
                for r in csv.DictReader(fh)
                if (r["Type"] or "").lower() == "control"}


class TestLevelMap:
    def test_level_for_is_1_or_2(self) -> None:
        assert level_for("JR2.C.1.1.5.1") == "2"     # /var/log partition
        assert level_for("JR2.C.4.2.7") == "1"        # SSH root login — baseline
        assert level_for("does-not-exist") == "1"     # default

    def test_every_level2_id_exists_in_the_referential(self) -> None:
        present = set(_controls())
        unknown = sorted(CIS_LEVEL_2 - present)
        assert not unknown, f"CIS_LEVEL_2 references unknown controls: {unknown}"

    def test_no_accidental_duplicates_or_empties(self) -> None:
        assert all(cid.strip() for cid in CIS_LEVEL_2)
        # a plain set already dedups; assert it's a sensible, faithful size
        assert 10 <= len(CIS_LEVEL_2) <= 40


class TestSeedReflectsLevels:
    def test_csv_matches_the_map(self) -> None:
        controls = _controls()
        # every control carries an explicit 1|2 — no blanks left
        assert all(v in ("1", "2") for v in controls.values()), "blank CIS Level remains"
        for cid, lvl in controls.items():
            assert lvl == level_for(cid), f"{cid}: CSV L{lvl} != map L{level_for(cid)}"

    def test_partition_family_is_level_2(self) -> None:
        controls = _controls()
        for cid in ("JR2.C.1.1.3.1", "JR2.C.1.1.5.1", "JR2.C.1.1.6.3", "JR2.C.1.1.7.2"):
            assert controls[cid] == "2", f"{cid} should be Level 2"

    def test_tmp_and_devshm_stay_level_1(self) -> None:
        # CIS keeps /tmp and /dev/shm at Level 1 — only /var* and /home are L2.
        controls = _controls()
        for cid in ("JR2.C.1.1.2.1", "JR2.C.1.1.2.2", "JR2.C.1.1.8.1", "JR2.C.1.1.8.3"):
            assert controls[cid] == "1", f"{cid} should be Level 1"

    def test_audit_tool_integrity_is_level_2(self) -> None:
        assert _controls()["JR2.C.5.1.3.1"] == "2"

    def test_critical_adds_a_meaningful_number_of_controls(self) -> None:
        controls = _controls()
        l2 = [c for c, v in controls.items() if v == "2"]
        # Critical must differ from Non-critical by a real, non-trivial set.
        assert len(l2) >= 10
