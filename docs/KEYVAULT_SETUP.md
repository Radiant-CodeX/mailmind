# Azure Key Vault Setup for MailMind

> **Security-first secrets management**: Move all sensitive credentials from `.env` files to Azure Key Vault so they're encrypted at rest, versioned, and auditable.

---

## Overview

The system automatically loads secrets from Key Vault when `AZURE_KEY_VAULT_URL` is set. If Key Vault is unavailable (or SDKs aren't installed), it falls back to `.env` silently. **No code changes needed** — the integration is already wired in.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ settings.py loads .env via load_dotenv()                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ keyvault.py calls load_keyvault_into_env()                  │
│   ↓ if AZURE_KEY_VAULT_URL is set                          │
│   ├─ DefaultAzureCredential authenticates                  │
│   ├─ Lists all secrets (dashes → underscores)              │
│   ├─ Sets os.environ with vault values (overrides .env)    │
│   ↓ if AZURE_KEY_VAULT_URL is NOT set or SDKs missing      │
│   └─ Falls back to .env (no error, graceful)               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ settings.py reads os.environ as usual                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Create the Key Vault

```bash
# Via Azure CLI (recommended)
az keyvault create \
  --name mailmind-vault \
  --resource-group your-rg \
  --location eastus2 \
  --enable-soft-delete true \
  --enable-purge-protection false

# Or via Azure Portal:
# Search "Key Vault" → Create
# Name: mailmind-vault, Region: eastus2
```

---

## Step 2: Add Secrets to the Vault

### Using the Setup Script (Recommended)

```bash
cd backend
bash scripts/setup-keyvault.sh
```

The script will prompt you interactively for each secret, then push them all to the vault. **Key Vault uses dashes in secret names**, but env vars use underscores — the script handles this automatically:

```
Key Vault secret name       →  Environment variable
AZURE-OPENAI-API-KEY       →  AZURE_OPENAI_API_KEY
SUPABASE-DB-PASSWORD       →  SUPABASE_DB_PASSWORD
DATABASE-URL               →  DATABASE_URL
...etc
```

### Or Manually (One at a Time)

```bash
VAULT_NAME=mailmind-vault

# Database
az keyvault secret set --vault-name $VAULT_NAME \
  --name DATABASE-URL \
  --value "postgresql://postgres:ctIGSbrZqk4G93d3@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require"

az keyvault secret set --vault-name $VAULT_NAME \
  --name SUPABASE-DB-PASSWORD \
  --value "ctIGSbrZqk4G93d3"

# Azure OpenAI
az keyvault secret set --vault-name $VAULT_NAME \
  --name AZURE-OPENAI-ENDPOINT \
  --value "https://your-resource.openai.azure.com/"

az keyvault secret set --vault-name $VAULT_NAME \
  --name AZURE-OPENAI-API-KEY \
  --value "your-api-key"

# Microsoft Graph
az keyvault secret set --vault-name $VAULT_NAME \
  --name AZURE-CLIENT-ID \
  --value "your-client-id"

az keyvault secret set --vault-name $VAULT_NAME \
  --name AZURE-CLIENT-SECRET \
  --value "your-client-secret"

# Google OAuth
az keyvault secret set --vault-name $VAULT_NAME \
  --name GOOGLE-CLIENT-ID \
  --value "your-google-client-id"

az keyvault secret set --vault-name $VAULT_NAME \
  --name GOOGLE-CLIENT-SECRET \
  --value "your-google-secret"

# Azure Language / other
az keyvault secret set --vault-name $VAULT_NAME \
  --name AZURE-LANGUAGE-KEY \
  --value "your-language-key"

# MailMind
az keyvault secret set --vault-name $VAULT_NAME \
  --name APPROVAL-TOKEN \
  --value "your-approval-token"

# Langsmith (optional)
az keyvault secret set --vault-name $VAULT_NAME \
  --name LANGSMITH-API-KEY \
  --value "your-langsmith-key"
```

---

## Step 3: Set Up Local Development

### For Local Dev (Using Service Principal)

1. **Create or get a Service Principal:**
   ```bash
   # If you don't have one, create it:
   az ad sp create-for-rbac --name mailmind-dev --role Contributor

   # Capture these values:
   # - appId → AZURE_CLIENT_ID
   # - password → AZURE_CLIENT_SECRET
   # - tenant → AZURE_TENANT_ID
   ```

2. **Copy `.env.local.example` to `.env.local`:**
   ```bash
   cp backend/.env.local.example backend/.env.local
   ```

3. **Fill in only the Key Vault auth vars** (the rest come from the vault):
   ```bash
   # backend/.env.local
   AZURE_KEY_VAULT_URL=https://mailmind-vault.vault.azure.net/
   AZURE_CLIENT_ID=your-sp-appid
   AZURE_CLIENT_SECRET=your-sp-password
   AZURE_TENANT_ID=common
   ```

4. **Grant the Service Principal access to the vault:**
   ```bash
   VAULT_NAME=mailmind-vault
   SP_OBJECT_ID=$(az ad sp show --id your-sp-appid --query objectId -o tsv)

   az keyvault set-policy --name $VAULT_NAME \
     --object-id $SP_OBJECT_ID \
     --secret-permissions get list
   ```

5. **Verify locally:**
   ```bash
   cd backend
   export $(cat .env.local | xargs)
   python -c "from app.config.settings import settings; print('✅ Loaded:', bool(settings.azure_openai_api_key))"
   ```

### For GitHub Actions CI/CD

Add these **repository secrets** in GitHub:
```
AZURE_KEY_VAULT_URL = https://mailmind-vault.vault.azure.net/
AZURE_CLIENT_ID = your-sp-appid
AZURE_CLIENT_SECRET = your-sp-password
AZURE_TENANT_ID = common
```

Then in `.github/workflows/ci.yml`:
```yaml
env:
  AZURE_KEY_VAULT_URL: ${{ secrets.AZURE_KEY_VAULT_URL }}
  AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
  AZURE_CLIENT_SECRET: ${{ secrets.AZURE_CLIENT_SECRET }}
  AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
```

---

## Step 4: Production Deployment (Managed Identity)

For Azure Container Instances, App Service, or AKS:

1. **Create a Managed Identity:**
   ```bash
   # For Container Instances
   az container create \
     --assign-identity /subscriptions/.../resourcegroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/mailmind-mi
   
   # For App Service
   az webapp identity assign --resource-group your-rg --name mailmind-api
   ```

2. **Grant the Managed Identity access to the vault:**
   ```bash
   VAULT_NAME=mailmind-vault
   MI_OBJECT_ID=$(az identity show --resource-group your-rg --name mailmind-mi --query principalId -o tsv)

   az keyvault set-policy --name $VAULT_NAME \
     --object-id $MI_OBJECT_ID \
     --secret-permissions get list
   ```

3. **Set only one env var in production:**
   ```bash
   AZURE_KEY_VAULT_URL=https://mailmind-vault.vault.azure.net/
   # Managed Identity authentication is automatic — no CLIENT_ID/SECRET needed
   ```

---

## Step 5: Verify Everything Works

### Dev Mode (with Service Principal in .env.local)

```bash
cd backend
# .env.local has AZURE_CLIENT_ID/SECRET
python -c "
import os
os.environ['AZURE_KEY_VAULT_URL'] = 'https://mailmind-vault.vault.azure.net/'
os.environ['AZURE_CLIENT_ID'] = 'your-sp-appid'
os.environ['AZURE_CLIENT_SECRET'] = 'your-sp-password'
os.environ['AZURE_TENANT_ID'] = 'common'

from app.config.settings import settings
print('✅ Loaded secrets from Key Vault')
print(f'   API Key: {settings.azure_openai_api_key[:20]}...')
print(f'   Client ID: {settings.azure_client_id}')
print(f'   DB URL: {settings.database_url[:50]}...')
"
```

### Production (Managed Identity automatic)

```bash
# In your container/app service — no special env vars needed beyond AZURE_KEY_VAULT_URL
# DefaultAzureCredential will use the Managed Identity automatically
AZURE_KEY_VAULT_URL=https://mailmind-vault.vault.azure.net/

# The backend loads secrets on startup
# Check logs:
docker logs <container-id> | grep "Loaded.*secret"
```

---

## Important Security Notes

### ✅ DO

- ✅ Store **all sensitive credentials** in Key Vault (API keys, secrets, passwords, tokens)
- ✅ Use **Managed Identity** in production (no CLIENT_ID/SECRET stored anywhere)
- ✅ Rotate secrets regularly via the vault
- ✅ Enable **soft delete** on the vault to prevent accidental deletion
- ✅ Enable **audit logging** to track secret access
- ✅ Keep `.env.local` out of git (`.gitignore` handles it)

### ❌ DON'T

- ❌ Commit `.env.local` or any file with secrets
- ❌ Paste secrets in Slack, emails, or logs
- ❌ Use the same Service Principal across multiple projects (create one per project)
- ❌ Share Managed Identity credentials (they're tied to the resource)
- ❌ Keep the setup script after running it (`rm scripts/setup-keyvault.sh`)
- ❌ Clear bash history after pasting secrets (`history -c`)

---

## Troubleshooting

### "Key Vault load failed"

1. Check the vault exists:
   ```bash
   az keyvault show --name mailmind-vault
   ```

2. Verify credentials are set:
   ```bash
   echo $AZURE_KEY_VAULT_URL $AZURE_CLIENT_ID $AZURE_CLIENT_SECRET
   ```

3. Check the service principal has access:
   ```bash
   az keyvault show-deleted --name mailmind-vault  # is it soft-deleted?
   az keyvault list-deleted  # list all deleted vaults
   ```

### "DefaultAzureCredential failed to authenticate"

Try each auth method in order:
```bash
# 1. Managed Identity (production)
az identity show --resource-group your-rg --name mailmind-mi

# 2. Service Principal env vars (dev)
az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant common

# 3. User login (fallback)
az login
```

### "Secret not found" / Empty env var

1. Verify the secret exists:
   ```bash
   az keyvault secret list --vault-name mailmind-vault
   ```

2. Check the secret name mapping (dashes ↔ underscores):
   ```bash
   # In vault: AZURE-OPENAI-API-KEY
   # In Python: settings.azure_openai_api_key
   ```

---

## Code Reference

### How It Works

**`app/config/keyvault.py`:**
```python
def load_keyvault_into_env() -> bool:
    vault_url = os.getenv("AZURE_KEY_VAULT_URL", "").strip()
    if not vault_url:
        return False  # No vault configured, use .env

    client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    for prop in client.list_properties_of_secrets():
        secret = client.get_secret(prop.name)
        # AZURE-OPENAI-API-KEY → AZURE_OPENAI_API_KEY
        env_key = prop.name.replace("-", "_").upper()
        os.environ[env_key] = secret.value or ""
    return True
```

**`app/config/settings.py`:**
```python
load_dotenv()  # .env loaded first
load_keyvault_into_env()  # vault secrets override (if configured)

class Settings:
    azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")  # from .env or vault
```

---

## Migration Checklist

- [ ] Create Key Vault (`az keyvault create`)
- [ ] Create Service Principal for local dev
- [ ] Add all secrets to the vault (use `scripts/setup-keyvault.sh`)
- [ ] Copy `.env.local.example` → `.env.local` and fill in SP credentials
- [ ] Test locally (`python -c "from app.config.settings import settings..."`)
- [ ] Delete `scripts/setup-keyvault.sh` (`rm backend/scripts/setup-keyvault.sh`)
- [ ] Update CI/CD secrets in GitHub
- [ ] Remove hardcoded secrets from `.env` (keep only non-sensitive config)
- [ ] For production: create Managed Identity and grant it vault access
- [ ] Verify in production logs: `Loaded X secret(s) from Azure Key Vault`
- [ ] ✅ Done! All credentials are now encrypted and auditable.
