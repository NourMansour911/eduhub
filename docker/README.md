# Docker Setup for EduHub

This directory contains the Docker setup for the EduHub project, including the API, reverse proxy, and data stores used in development.

## Services Overview

- API (FastAPI): main backend running with Uvicorn (built from `docker/api/Dockerfile`).
- Nginx: reverse proxy in front of the API (`docker/nginx/default.conf`).
- MongoDB: primary document database.
- Qdrant: vector database for embeddings and semantic search.
- Redis: cache/session store.

> Note: The compose file is at `docker/docker-compose.yml` and uses named volumes for persistence.

## Environment files

Before starting services, create required env files from the examples. Run these from the project root:

```bash
cd docker/env
cp .env.example.app .env.app
cp .env.example.mongodb .env.mongodb
cp .env.example.redis .env.redis
```

There is also an optional project-level `.env` if you prefer. Example:

```bash
cd docker
cp .env.example .env
```

Important env keys are referenced by the compose file and API container. Keep secrets out of version control.

## Build & Run

From the project root run (recommended):

```bash
# Build and start all services in background
docker compose -f docker/docker-compose.yml up --build -d

# Tail logs
docker compose -f docker/docker-compose.yml logs -f --tail=200 api
```

Or from inside the `docker/` folder:

```bash
cd docker
docker compose up --build -d
```

To start only core services:

```bash
docker compose -f docker/docker-compose.yml up -d api nginx mongodb qdrant redis
```

If you run into dependency/startup ordering issues, start databases first then the app:

```bash
# Start DBs first
docker compose -f docker/docker-compose.yml up -d mongodb qdrant redis
# Wait for readiness (adjust sleep as needed)
sleep 20
# Start API and proxy
docker compose -f docker/docker-compose.yml up -d --build api nginx
```

## Notes about the API image build

- The API Dockerfile is multi-stage (`docker/api/Dockerfile`) to keep the runtime image smaller. Build tools and heavy wheel compilation happen in the builder stage and are not copied to runtime.
- `constraints-docker.txt` is referenced during the build to pin versions; if not present a placeholder file is used so the build doesn't fail on COPY.
- A CPU wheel index is used for some packages (e.g., PyTorch CPU wheels) to avoid CUDA dependencies in the image.
- The Dockerfile performs a `python -m spacy download en_core_web_sm` during build; the build requires internet access and may take time.

## Accessing services

- API: http://localhost:8000
- API docs (FastAPI): http://localhost:8000/docs
- Nginx proxy (root host): http://localhost
- Qdrant dashboard: http://localhost:6333/dashboard (if Qdrant dashboard enabled)
- MongoDB: mongodb://localhost:27017 (client tools) — credentials come from `docker/env/.env.mongodb`
- Redis: redis://localhost:6379 (password is in `docker/env/.env.redis`)

## Volumes and data management

The compose uses named volumes. Useful commands:

```bash
# List volumes
docker volume ls

# Inspect a specific volume
docker volume inspect eduhub_mongodata

# Remove a single volume
docker volume rm eduhub_api_data

# Prune unused volumes (destructive)
docker volume prune
```

To backup a named volume to a tar file:

```bash
docker run --rm -v eduhub_mongodata:/volume -v $(pwd):/backup alpine sh -c "cd /volume && tar cvf /backup/mongo_backup.tar ."
```

## Troubleshooting

- Check container status and logs:

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs --tail=200 api
docker compose -f docker/docker-compose.yml logs --tail=200 mongodb
docker compose -f docker/docker-compose.yml logs --tail=200 qdrant
docker compose -f docker/docker-compose.yml logs --tail=200 redis
```

- If the API fails to connect to a DB, verify the env file values and container names used in `docker-compose.yml` (e.g. `mongodb`, `qdrant`, `chat-redis`).
- If `spacy` or `torch` install fails during build, re-run build with more build-time resources or pin versions that have wheel distribution available.

## Development workflow

The API container is built with source copied into the image at build time. After code changes, rebuild the image:

```bash
# Rebuild API only
docker compose -f docker/docker-compose.yml up -d --build api

# Or build locally
docker build -f docker/api/Dockerfile -t eduhub-api:local ..
```

## Security & cleanup

- The provided example envs include secrets for local testing only—rotate or remove secrets before sharing code.
- To remove all containers and named volumes for a clean start:

```bash
docker compose -f docker/docker-compose.yml down -v --remove-orphans
```


---

If you want, I can:

- add small healthchecks to the `docker-compose.yml` for mongodb/qdrant/redis;
- add a simple `wait-for` script in the API image to block startup until DBs are reachable;
- run a local `docker compose up --build` here and report build logs (if you permit running commands).
