"""Sensitive platform_config values are encrypted at rest; reads decrypt."""
from __future__ import annotations

from sqlalchemy import select

from infrastructure.database.adapter import (
    PlatformConfigRepository, create_db, platform_config_table,
)
from infrastructure.security.crypto import SecretBox


async def _raw(session_factory, key):
    async with session_factory() as s:
        row = (await s.execute(
            select(platform_config_table).where(platform_config_table.c.key == key)
        )).first()
        return row.value if row else None


async def test_secret_encrypted_at_rest(tmp_path):
    _, sf = await create_db(str(tmp_path / "t.db"))
    repo = PlatformConfigRepository(sf, secret_box=SecretBox("master"))

    await repo.set("detection_webhook_api_key", "sabc_topsecret")
    stored = await _raw(sf, "detection_webhook_api_key")
    assert stored != "sabc_topsecret"
    assert stored.startswith("enc:v1:")
    assert await repo.get("detection_webhook_api_key") == "sabc_topsecret"


async def test_non_secret_stays_plaintext(tmp_path):
    _, sf = await create_db(str(tmp_path / "t2.db"))
    repo = PlatformConfigRepository(sf, secret_box=SecretBox("m"))
    await repo.set("puppet_edition", "core")
    assert await _raw(sf, "puppet_edition") == "core"
    assert await repo.get("puppet_edition") == "core"


async def test_legacy_plaintext_still_readable(tmp_path):
    _, sf = await create_db(str(tmp_path / "t3.db"))
    # Simulate a pre-encryption database: write plaintext with a box-less repo.
    await PlatformConfigRepository(sf).set("pe_console_password", "oldplain")
    # An encrypting repo must still read the legacy plaintext transparently.
    enc = PlatformConfigRepository(sf, secret_box=SecretBox("m"))
    assert await enc.get("pe_console_password") == "oldplain"


async def test_rewrite_upgrades_to_ciphertext(tmp_path):
    _, sf = await create_db(str(tmp_path / "t4.db"))
    await PlatformConfigRepository(sf).set("pe_console_password", "oldplain")
    enc = PlatformConfigRepository(sf, secret_box=SecretBox("m"))
    await enc.set("pe_console_password", "rotated")
    assert (await _raw(sf, "pe_console_password")).startswith("enc:v1:")
    assert await enc.get("pe_console_password") == "rotated"
