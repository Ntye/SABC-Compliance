#!/usr/bin/env python3
"""
Regenerate the committed SABC Baseline seed (``sabc_baseline.csv``) from the
source spreadsheet.

The spreadsheet ships complete Debian-family guidance and empty Red Hat-family
columns; this script fills the Red Hat columns via ``redhat_translation`` so the
built-in referential is complete for both families, then writes a CSV in the
canonical unified-referential column order. The CSV — not the xlsx — is what the
platform importer seeds from at first boot, so it is committed and reviewable.

Usage:
    python3 generate_seed.py            # regenerate sabc_baseline.csv in place
    python3 generate_seed.py --report   # also print a per-family coverage report

Requires openpyxl only for regeneration; the platform itself never imports it.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from authored_remediations import REMEDIATIONS  # noqa: E402
from control_levels import level_for  # noqa: E402
from redhat_translation import PROV_AUTHORED, derive_redhat  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "Referentiel_Template_multiOS.xlsx")
SHEET = "Example - Unified referential"
CSV_OUT = os.path.join(HERE, "sabc_baseline.csv")

# Canonical column order for the unified referential (also what the importer
# reads). "Control Key" is auto-derived from Control ID at import time; it is
# emitted for readability but the importer ignores any provided value.
COLUMNS = [
    "Control ID", "Control Key", "Type", "Section", "Title", "Applies To",
    "CIS Level", "Framework Reference", "Agreed Value", "Description",
    "Security Rationale",
    "Validate — Debian family", "Configure — Debian family",
    "Validate — Red Hat family", "Configure — Red Hat family",
]


def _slug(control_id: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (control_id or "").strip().lower()).strip("_")


def load_rows() -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, data_only=True)
    ws = wb[SHEET]
    raw = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c is not None else "" for c in raw[0]]
    idx = {h: i for i, h in enumerate(header)}

    def cell(row, name):
        i = idx.get(name)
        v = row[i] if i is not None and i < len(row) else None
        return "" if v is None else str(v).strip()

    out: list[dict] = []
    for row in raw[1:]:
        if not any(c is not None and str(c).strip() for c in row):
            continue
        out.append({
            "control_id": cell(row, "Control ID"),
            "type": (cell(row, "Type") or "control").lower(),
            "section": cell(row, "Section"),
            "title": cell(row, "Title"),
            "applies_to": cell(row, "Applies To"),
            "cis_level": cell(row, "CIS Level"),
            "framework_reference": cell(row, "Framework Reference"),
            "agreed_value": cell(row, "Agreed Value"),
            "description": cell(row, "Description"),
            "rationale": cell(row, "Security Rationale"),
            "validate_debian": cell(row, "Validate — Debian family"),
            "configure_debian": cell(row, "Configure — Debian family"),
        })
    return out


def build(report: bool = False) -> list[list[str]]:
    rows = load_rows()

    # Guard: every Level-2 id must be a real control in the source — a typo
    # would silently leave a control at Level 1 and skew the tiers.
    from control_levels import CIS_LEVEL_2
    control_ids = {r["control_id"] for r in rows if r["type"] == "control"}
    unknown_l2 = sorted(CIS_LEVEL_2 - control_ids)
    if unknown_l2:
        raise SystemExit(f"control_levels.CIS_LEVEL_2 references unknown controls: {unknown_l2}")

    stats = {"authored": 0, "derived": 0, "empty": 0}
    pending: list[str] = []
    out_rows: list[list[str]] = [COLUMNS]

    for r in rows:
        cid = r["control_id"]
        is_control = r["type"] == "control"
        applies = (r["applies_to"] or "debian;redhat").lower()
        redhat_in_scope = "redhat" in applies

        # Authored remediations replace the spreadsheet's Debian cells BEFORE
        # the Red Hat derivation, so the derived guidance ports the corrected
        # procedure; explicitly-authored Red Hat cells bypass derivation.
        authored = REMEDIATIONS.get(cid) if is_control else None
        if authored:
            r["validate_debian"] = authored.get("validate_debian", r["validate_debian"])
            r["configure_debian"] = authored.get("configure_debian", r["configure_debian"])

        v_rh = c_rh = ""
        if is_control and redhat_in_scope:
            v_rh, pv = derive_redhat(cid, "validate", r["validate_debian"])
            c_rh, pc = derive_redhat(cid, "configure", r["configure_debian"])
            if authored and "validate_redhat" in authored:
                v_rh, pv = PROV_AUTHORED + authored["validate_redhat"], "authored"
            if authored and "configure_redhat" in authored:
                c_rh, pc = PROV_AUTHORED + authored["configure_redhat"], "authored"
            for p, fld in ((pv, "validate"), (pc, "configure")):
                stats[p] = stats.get(p, 0) + 1
                if p == "empty":
                    pending.append(f"{cid}/{fld}")

        # Authoritative CIS level: controls get their real Level (1|2) from the
        # curated map; section rows carry no level. This overrides the blank /
        # inconsistent values in the source spreadsheet so the tiers are real.
        cis_level = level_for(cid) if is_control else ""

        out_rows.append([
            cid, _slug(cid), r["type"], r["section"], r["title"],
            r["applies_to"] or "debian;redhat", cis_level,
            r["framework_reference"], r["agreed_value"], r["description"],
            r["rationale"],
            r["validate_debian"], r["configure_debian"], v_rh, c_rh,
        ])

    if report:
        controls = [r for r in rows if r["type"] == "control"]
        n_l2 = sum(1 for r in controls if r["control_id"] in CIS_LEVEL_2)
        print(f"Source rows: {len(rows)} ({len(controls)} controls, "
              f"{len(rows) - len(controls)} sections)")
        print(f"CIS level — Level 1: {len(controls) - n_l2}, Level 2: {n_l2} "
              f"(Non-critical enforces L1; Critical adds the {n_l2} L2 controls)")
        print(f"Red Hat cells — authored: {stats['authored']}, "
              f"derived (mechanical): {stats['derived']}, empty: {stats['empty']}")
        authored_ids = sorted({
            r["control_id"] for r in controls
            if "redhat" in (r["applies_to"] or "debian;redhat").lower()
            and __import__("redhat_translation").OVERRIDES.get(r["control_id"])
        })
        print(f"Authored-override controls ({len(authored_ids)}): {', '.join(authored_ids)}")
        if pending:
            print(f"IMPLEMENTATION PENDING (empty Debian source): {pending}")
        else:
            print("No implementation-pending cells — both families complete.")
    return out_rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="print coverage report")
    args = ap.parse_args()

    out_rows = build(report=args.report)
    with open(CSV_OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerows(out_rows)
    print(f"Wrote {len(out_rows) - 1} rows → {os.path.relpath(CSV_OUT, HERE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
