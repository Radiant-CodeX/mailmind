"""Azure Key Vault secret loader.

Production secrets-hygiene pattern: when `AZURE_KEY_VAULT_URL` is set, secrets
are pulled from Key Vault into the process environment so the rest of the app
reads them exactly like local `.env` values. When the variable is absent (or the
optional Azure SDKs aren't installed), it silently falls back to `.env`.

Key Vault secret names can't contain underscores, so a secret named
`AZURE-OPENAI-API-KEY` maps to the env var `AZURE_OPENAI_API_KEY`.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("mailmind.keyvault")


def load_keyvault_into_env() -> bool:
    """Load Key Vault secrets into os.environ. Returns True if any were loaded.

    Key Vault is authoritative when configured: its values override `.env` so a
    deployed instance always uses the vault. No-op (returns False) when
    `AZURE_KEY_VAULT_URL` is unset.
    """
    vault_url = os.getenv("AZURE_KEY_VAULT_URL", "").strip()
    if not vault_url:
        return False

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except Exception:
        logger.warning(
            "AZURE_KEY_VAULT_URL is set but azure-identity/azure-keyvault-secrets "
            "are not installed — falling back to environment/.env."
        )
        return False

    try:
        # additionally_allowed_tenants="*" lets the credential work even when
        # AZURE_TENANT_ID is set to "common" or a different tenant than the vault's.
        client = SecretClient(
            vault_url=vault_url,
            credential=DefaultAzureCredential(additionally_allowed_tenants=["*"]),
        )
        loaded = 0
        for prop in client.list_properties_of_secrets():
            secret = client.get_secret(prop.name)
            env_key = prop.name.replace("-", "_").upper()
            os.environ[env_key] = secret.value or ""
            loaded += 1
        logger.info("Loaded %d secret(s) from Azure Key Vault (%s)", loaded, vault_url)
        return loaded > 0
    except Exception as exc:  # pragma: no cover - network/permission dependent
        # Common causes: vault not created yet, wrong URL, no auth credentials set
        logger.warning(
            "Key Vault load failed — falling back to environment/.env. "
            "Cause: %s. Run 'bash scripts/setup-keyvault.sh' to populate the vault.",
            exc,
        )
        return False
