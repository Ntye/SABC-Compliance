"""Multi-distribution family normalization.

Regression cover for the RedHat-family scan bug: EC2's default distro is Amazon
Linux, whose /etc/os-release ID is 'amzn' (often with no ID_LIKE) and whose
InSpec/train family string is 'amazon' — neither of which the old code mapped to
'redhat', so a RHEL-compatible node resolved to no applicable controls and the
scan effectively did nothing.
"""
from __future__ import annotations

import pytest

from core.domain.entities import normalize_family


class TestRedHatFamily:
    @pytest.mark.parametrize("value", [
        "RedHat", "redhat", "rhel", "centos", "rocky", "almalinux", "alma",
        "fedora", "amazon", "amzn", "oracle", "ol", "oraclelinux",
        "scientific", "cloudlinux",
    ])
    def test_maps_to_redhat(self, value: str) -> None:
        assert normalize_family(value) == "redhat"


class TestDebianFamily:
    @pytest.mark.parametrize("value", [
        "Debian", "debian", "ubuntu", "mint", "linuxmint", "raspbian", "kali", "pop",
    ])
    def test_maps_to_debian(self, value: str) -> None:
        assert normalize_family(value) == "debian"


class TestUnknown:
    def test_blank_is_none(self) -> None:
        assert normalize_family("") is None
        assert normalize_family(None) is None

    def test_genuinely_foreign_family_passes_through_lowercased(self) -> None:
        # SUSE is a real but unsupported family — surfaced (not silently RedHat)
        # so resolution can treat it as out-of-scope rather than mis-scan it.
        assert normalize_family("SLES") == "sles"
