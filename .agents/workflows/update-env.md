---
name: update-env
description: "Synchronize and validate .env files across local, docker, and deploy environments, keep settings.py in sync, update .example templates without secrets, and ensure docker-compose alignment."
---

# Environment & Docker Compose Synchronization Workflow (`/update-env`)

Use this workflow whenever any environment variable is added, updated, or removed, or when aligning Docker compose and deployment environments.

---

## 🗺️ Environment Architecture & Source of Truth

```
   [src/.env] (Local Development - Source of Truth for App Variables)
       │
       ├──► 1. [src/core/settings.py] (Pydantic BaseSettings validation)
       │
       ├──► 2. [src/.env.example] (Sanitized template - NO secrets/keys)
       │
       └──► 3. [docker/env/.env.app] (Container App Env - Service Hosts + Verbatim Secrets)
                   │
                   ├──► 4. [docker/env/.env.example.app] (Sanitized docker app template)
                   │
                   └──► 5. [deploy/env/] (Exact 1:1 Mirror of docker/env/ for team/server deployment)

   [docker/docker-compose.yml] (Main Compose - Source of Truth for Services)
       │
       ├──► 6. [docker/docker-compose.example.yml] (Example Compose - compatible services & networks)
       │
       └──► 7. [deploy/docker-compose.yml] (Deployment Compose - prebuilt image + production storage)
```

---

## 📋 Step-by-Step Execution Guide for Agent

### Step 1: Inspect Changes in `src/.env`
1. Review recent modifications in `src/.env` (using git diff or reading the file).
2. Identify all:
   - Added variables.
   - Modified variable values (especially credentials, endpoints, or model IDs).
   - Removed or deprecated variables.

---

### Step 2: Validate & Update `src/core/settings.py`
1. Read `src/core/settings.py` and inspect the `Settings` class (inherits from `pydantic_settings.BaseSettings`).
2. Verify that **every single non-commented variable** present in `src/.env` has a corresponding field defined in `Settings`.
3. If a variable is missing in `settings.py`:
   - Add it to `Settings` with the appropriate type (`str`, `int`, `bool`, `Optional[str] = None`).
   - If it has an existing default or optional fallback, specify it (e.g. `HF_TOKEN: Optional[str] = None`).
4. If a variable was removed or renamed in `src/.env`, check if references in `src/` need updating and adjust `settings.py` accordingly.

---

### Step 3: Synchronize `docker/env/.env.app`
1. Compare `src/.env` with `docker/env/.env.app`.
2. **Translate Localhost Service URLs to Docker Network Hostnames**:
   Inside Docker containers, internal dependencies must use their Docker network service or container names rather than `localhost`:

   | Service | Localhost Host (`src/.env`) | Docker Service Host (`docker/env/.env.app`) | Example in `.env.app` |
   | :--- | :--- | :--- | :--- |
   | **MongoDB** | `localhost:27017` | `mongodb:27017` | `mongodb://eduhubadmin:pass@mongodb:27017/?authSource=admin` |
   | **Qdrant** | `localhost:6333` | `qdrant:6333` | `http://qdrant:6333` |
   | **Redis** | `localhost:6379` | `chat-redis:6379` | `redis://:pass@chat-redis:6379` |

3. **External Services (Do NOT translate)**:
   External endpoints (e.g., Azure Document Intelligence, OpenRouter `https://openrouter.ai/api/v1`, remote databases like `eduhub.onlinewebshop.net`) remain **identical**.
4. **Verbatim Transfer of Secrets**:
   > [!IMPORTANT]
   > All API keys (`OPENAI_API_KEY`, `COHERE_API_KEY`, `AZURE_DOC_KEY`, `LANGSMITH_API_KEY`, `HF_TOKEN`), tokens, passwords, and model parameters must be copied **strictly verbatim (letter-for-letter)** without modifications or truncation.

---

### Step 4: Mirror `docker/env/` to `deploy/env/`
`deploy/env/` is designed for distributing deployment secrets to collaborators or staging/production environments running Docker.

1. Inspect the files in `docker/env/`:
   - `.env.app`
   - `.env.mongodb`
   - `.env.redis`
   - `.env.grafana` (if present)
   - `.env.example.*` files
2. Ensure that **every single file** in `docker/env/` is mirrored into `deploy/env/`.
3. Contents of corresponding `.env` files in `deploy/env/` must be an **exact, byte-for-byte copy** of `docker/env/`, ensuring zero secret discrepancies between local Docker tests and deployment.

---

### Step 5: Generate & Update All `.example` Files
Every `.env` file must have a synchronized `.example` counterpart so that new developers can spin up the project without exposing real credentials in source control.

1. Files to maintain:
   - `src/.env` ➔ `src/.env.example`
   - `docker/env/.env.app` ➔ `docker/env/.env.example.app`
   - `docker/env/.env.mongodb` ➔ `docker/env/.env.example.mongodb`
   - `docker/env/.env.redis` ➔ `docker/env/.env.example.redis`
   - `docker/env/.env.grafana` ➔ `docker/env/.env.example.grafana`

2. **Sanitization Rules for `.example` files**:
   - **Retain structure and non-sensitive configurations**: Keep `APP_NAME`, `APP_VERSION`, `STORAGE_PATH`, `GENERATION_BACKEND`, `GENERATION_MODEL_ID`, `EMBEDDING_MODEL_ID`, `EMBEDDING_MODEL_SIZE`, `VECTOR_DB_BACKEND`, `VECTOR_DB_DISTANCE_METHOD`, booleans, and public API endpoint URLs.
   - **Strip all secrets and API keys**: Set them to empty (`KEY=`):
     - `AZURE_DOC_KEY=`
     - `AZURE_DOC_ENDPOINT=`
     - `COHERE_API_KEY=`
     - `OPENAI_API_KEY=`
     - `LANGSMITH_API_KEY=`
     - `HF_TOKEN=`
     - `MONGO_INITDB_ROOT_PASSWORD=`
     - `REDIS_PASSWORD=`
     - `GF_SECURITY_ADMIN_PASSWORD=`
   - **Sanitize connection strings containing embedded passwords**:
     - `MONGODB_URL=` (leave blank or generic without credentials)
     - `REDIS_URL=` / `REDIS_ADDR=` (leave blank)
     - `DB_BASE_URL=` (leave blank)
   - Ensure commented-out API key alternates (e.g. `# OPENAI_API_KEY=...`) have their secret tokens cleared.

---

### Step 6: Synchronize Docker Compose Configurations

Source of truth: `docker/docker-compose.yml`.

1. **Verify and Update `docker/docker-compose.example.yml`**:
   - Must use the identical service architecture: `api`, `qdrant`, `mongodb`, `redis`.
   - Must reference the correct network (`backend`) and persistent volumes (`eduhub_qdrant_data`, `eduhub_mongodata`, `eduhub_redis_data`).
   - Must point `env_file:` to the proper locations:
     - `api`: `./env/.env.app` (or `./env/.env.example.app`)
     - `mongodb`: `./env/.env.mongodb` (or `./env/.env.example.mongodb`)
     - `redis`: `./env/.env.redis` (or `./env/.env.example.redis`)
   - Include clear header instructions for copying `.env.example.*` to `.env.*`.

2. **Verify and Update `deploy/docker-compose.yml`**:
   - Production differences from `docker/docker-compose.yml`:
     - Uses published image: `image: nourmansour41/eduhub:latest` instead of `build:`.
     - Uses named storage volume: `app_storage:/app/storage` instead of local mount `../storage:/app/storage`.
   - All other services (`qdrant`, `mongodb`, `redis`), ports (`81:81`, `6333:6333`, `27017:27017`, `6379:6379`), container names, `depends_on`, commands, networks (`backend`), and `env_file` paths must stay in **complete lockstep** with `docker/docker-compose.yml`.

---

### Step 7: Final Verification Checklist
Run through this checklist before concluding the turn:
- [ ] Are all variables in `src/.env` represented in `src/core/settings.py`?
- [ ] Are Docker service host names (`mongodb`, `qdrant`, `chat-redis`) correctly set in `docker/env/.env.app`?
- [ ] Were all secrets copied verbatim into `docker/env/.env.app`?
- [ ] Is `deploy/env/` identical to `docker/env/`?
- [ ] Are all `.example` files updated with all config keys, while having secrets stripped?
- [ ] Do `docker-compose.example.yml` and `deploy/docker-compose.yml` reflect all changes from `docker/docker-compose.yml`?
