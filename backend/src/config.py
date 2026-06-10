from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    port: int = 3000
    host_ip: str = ""            # Platform host's LAN IP; auto-detected when blank
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1",
        "http://127.0.0.1:80",
    ]

    # Storage
    db_path: str = "./data/platform.db"
    ssh_key_path: str = "./keys/ansible_id_rsa"
    ansible_dir: str = "./ansible"
    packages_dir: str = "./packages"

    # JWT (username/password auth)
    jwt_secret: str = "change-me-in-production-use-random-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Puppet
    puppet_edition: str = "enterprise"          # "enterprise" | "community"
    puppet_master_host: str | None = None
    puppet_master_port: int | None = None       # auto-selects 8143 (PE) or 8140 (OSS) when None
    puppet_rbac_port: int = 4433
    puppet_admin_user: str = "admin"
    puppet_admin_pass: str | None = None
    puppet_token_lifetime: int = 1296000
    puppet_token_rotate_seconds: int = 43200

    # Wazuh
    wazuh_manager_host: str | None = None
    wazuh_api_port: int = 55000
    wazuh_api_user: str = "wazuh"
    wazuh_api_pass: str | None = None
    wazuh_reg_port: int = 1515
    wazuh_agent_port: int = 1514
    wazuh_webhook_source_ip: str | None = None
    wazuh_token_refresh_seconds: int = 840

    # Collection
    collector_interval_seconds: int = 300

    # Features
    swagger_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
