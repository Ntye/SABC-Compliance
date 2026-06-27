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
    # Full async DSN — overrides db_path when set.
    # SQLite (default):   leave blank
    # PostgreSQL:         postgresql+asyncpg://sabc:secret@postgres:5432/sabc
    database_url: str = ""
    ssh_key_path: str = "./keys/ansible_id_rsa"
    ansible_dir: str = "./ansible"
    packages_dir: str = "./packages"
    # Directory holding the frontend's TLS cert/key (server.crt / server.key).
    # Shared with the frontend container via the frontend-certs Docker volume so
    # an operator can install a CA-signed certificate through the UI. The
    # frontend's entrypoint watches this directory and reloads nginx on change.
    tls_certs_dir: str = "/app/certs"

    # JWT (username/password auth)
    jwt_secret: str = "change-me-in-production-use-random-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # Puppet Enterprise
    puppet_master_host: str | None = None
    puppet_master_port: int = 8143
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
    # Shared secret presented by Wazuh's integrator in the X-Wazuh-Webhook-Token
    # header. When unset the webhook is DISABLED (closed by default) — no alert is
    # ever processed without an explicitly configured secret.
    wazuh_webhook_secret: str | None = None
    # Only alerts at or above this Wazuh rule level trigger the active-response
    # remediation loop. Wazuh levels: 7+ ≈ important, 10+ ≈ high, 12+ ≈ critical.
    wazuh_webhook_min_level: int = 7
    # Re-run a compliance scan on the node after remediation completes, so the
    # dashboard reflects the post-enforcement state automatically.
    wazuh_webhook_rescan: bool = True
    wazuh_token_refresh_seconds: int = 840

    # Collection
    collector_interval_seconds: int = 300

    # Offline AI assistant (Ollama)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Features
    swagger_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
