"""
Section 0 — seed the built-in SABC Baseline referential at first boot.

The unified referential ships in-repo (``platform/seed/referentials/sabc_baseline/
sabc_baseline.csv``) and is imported through the SAME UPSERT importer used for
runtime imports — there is no special seeding path. The seeded profile is a
SYSTEM built-in: undeletable, but re-seedable (a new committed CSV with a bumped
seed marker re-imports on the next boot, upserting changed controls and retiring
removed ones).
"""
from __future__ import annotations

import logging
import os

from core.domain.entities import SABC_BASELINE_PROFILE_ID
from core.domain.interfaces import IPlatformConfigRepository, IProfileRepository

from .referential_importer import ReferentialImportUseCase, parse_referential_csv

logger = logging.getLogger(__name__)

# Bump when the committed seed CSV changes to trigger a re-import on next boot.
SEED_VERSION = "1.0.0"
_SEED_MARKER_KEY = "sabc_baseline_seed_version"

_SEED_FILENAME = "sabc_baseline.csv"


def _candidate_dirs() -> list[str]:
    """Where the committed seed CSV may live (env override → repo → image)."""
    here = os.path.dirname(os.path.abspath(__file__))
    # backend/src/modules/profiles → repo root is five levels up.
    repo_root = os.path.abspath(os.path.join(here, "..", "..", "..", ".."))
    return [
        os.environ.get("REFERENTIAL_SEED_DIR", "").strip(),
        # The seed now lives under backend/platform (shipped in the image at
        # /app/platform); keep the old top-level path as a fallback.
        os.path.join(repo_root, "backend", "platform", "seed", "referentials", "sabc_baseline"),
        os.path.join(repo_root, "platform", "seed", "referentials", "sabc_baseline"),
        "/app/platform/seed/referentials/sabc_baseline",
    ]


def _find_seed_csv() -> str | None:
    for d in _candidate_dirs():
        if not d:
            continue
        path = os.path.join(d, _SEED_FILENAME)
        if os.path.isfile(path):
            return path
    return None


class SeedSabcBaselineUseCase:
    """Idempotently import the built-in SABC Baseline as a system profile."""

    def __init__(self, profile_repo: IProfileRepository,
                 config_repo: IPlatformConfigRepository) -> None:
        self._repo = profile_repo
        self._cfg = config_repo
        self._importer = ReferentialImportUseCase(profile_repo)

    async def execute(self) -> dict | None:
        csv_path = _find_seed_csv()
        if not csv_path:
            logger.warning(
                "SABC Baseline seed CSV not found (looked in %s) — skipping seed",
                [d for d in _candidate_dirs() if d],
            )
            return None

        existing = await self._repo.find_by_id(SABC_BASELINE_PROFILE_ID)
        marker = None
        try:
            marker = await self._cfg.get(_SEED_MARKER_KEY)
        except Exception:
            marker = None

        # Already seeded at the current version → nothing to do (avoids churning
        # edit history on every restart).
        if existing is not None and marker == SEED_VERSION:
            return None

        with open(csv_path, encoding="utf-8") as fh:
            text = fh.read()
        errors: list[str] = []
        rows = parse_referential_csv(text, errors)
        if errors:
            logger.error("SABC Baseline seed CSV invalid: %s", errors[:5])
            return None

        summary = await self._importer.import_referential(
            rows,
            profile_id=SABC_BASELINE_PROFILE_ID,
            name="SABC Baseline",
            description=(
                "Unified multi-OS SABC hardening referential (built-in). "
                "Controls carry per-family Debian and Red Hat guidance; scope is "
                "decided by each control's CIS Level and each node's tier."
            ),
            version=SEED_VERSION,
            source="builtin",
            is_system=True,
        )
        try:
            await self._cfg.set(_SEED_MARKER_KEY, SEED_VERSION)
        except Exception:
            pass
        logger.info(
            "Seeded SABC Baseline (built-in, system) v%s: %d controls "
            "(+%d ~%d retired=%d)",
            SEED_VERSION, summary["control_count"],
            summary["created"], summary["updated"], summary["retired"],
        )
        return summary
