# Docker Setup for EduHub

This directory contains the Docker setup for the EduHub project with a pre-built image and all required services (API, MongoDB, Qdrant, Redis, Nginx).

---

## Quick Start: Using the Pre-built Image

The easiest way to get started is with the pre-built Docker image (`nourmansour41/eduhub:latest`) and the included `docker-compose.example.yml`:

```bash
# 1. Copy the example compose file
cp docker-compose.example.yml docker-compose.yml

# 2. Create environment files
cd env
cp .env.example.app .env.app
cp .env.example.mongodb .env.mongodb
cp .env.example.redis .env.redis
cd ..

# 3. Start all services
docker compose up -d
```

That's it! All services will start automatically.

## What You Get

The `docker-compose.example.yml` sets up these services:

| Service | Image | Purpose | Port |
|---------|-------|---------|------|
| **API** | `nourmansour41/eduhub:latest` | FastAPI backend with Uvicorn | 8000 |
| **Nginx** | `nginx:latest` | Reverse proxy & load balancer | 80 |
| **MongoDB** | `mongo:7.0` | Document database | 27017 |
| **Qdrant** | `qdrant/qdrant:latest` | Vector database for embeddings | 6333 |
| **Redis** | `redis:7-alpine` | Cache & session store | 6379 |

All services run on the `eduhub-network` bridge network and persist data using named volumes.

## Accessing Services

Once running, access your services here:

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Nginx (Root)**: http://localhost
- **Qdrant Dashboard**: http://localhost:6333/dashboard
- **MongoDB**: `mongodb://localhost:27017` (credentials from `.env.mongodb`)
- **Redis**: `redis://localhost:6379` (password from `.env.redis`)

## Environment Files

Create environment files in the `docker/env/` folder. The compose file reads these automatically:

```bash
cd docker/env
cp .env.example.app .env.app
cp .env.example.mongodb .env.mongodb
cp .env.example.redis .env.redis
```

**Keep secrets out of version control!** The example envs are for local testing only.

---

## Building Your Own Image

If you want to build the API image locally instead of using the pre-built one, follow this section.

### How the Image is Built

The image is created using a **multi-stage Dockerfile** (`docker/api/Dockerfile`) that optimizes for size and speed:

1. **Builder Stage**: Installs build tools and compiles Python dependencies (heavy compilation happens here)
2. **Runtime Stage**: Copies only the compiled wheels and source code (no build tools included)

This keeps the final image small and fast.

### Build Details

- **Constraints file**: `constraints-docker.txt` pins dependency versions for reproducible builds
- **spaCy model**: Downloads `en_core_web_sm` during build (requires internet, takes time)
- **PyTorch CPU**: Uses CPU wheel index to avoid CUDA bloat
- **Build time**: ~5-10 minutes depending on internet and system

### Building Locally

From the project root:

```bash
# Build the API image
docker build -f docker/api/Dockerfile -t eduhub-api:local ..

# Or use compose to build and start
docker compose -f docker/docker-compose.yml up --build -d
```

Then update `docker-compose.yml` to use your local image:

```yaml
services:
  api:
    image: eduhub-api:local  # Instead of nourmansour41/eduhub:latest
```

---

## Advanced Usage

### Build & Run

### Build & Run

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

### Development Workflow

The API container is built with source copied into the image at build time. After code changes, rebuild the image:

```bash
# Rebuild API only
docker compose -f docker/docker-compose.yml up -d --build api

# Or build locally
docker build -f docker/api/Dockerfile -t eduhub-api:local ..
```

---

## Volumes and Data Management

The compose uses named volumes for data persistence. Useful commands:

```bash
# List volumes
docker volume ls

# Inspect a specific volume
docker volume inspect eduhub_mongo_data

# Remove a single volume
docker volume rm eduhub_mongo_data

# Prune unused volumes (destructive)
docker volume prune
```

To backup a named volume to a tar file:

```bash
docker run --rm -v eduhub_mongo_data:/volume -v $(pwd):/backup alpine sh -c "cd /volume && tar cvf /backup/mongo_backup.tar ."
```

---

## Troubleshooting

- Check container status and logs:

```bash
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs --tail=200 api
docker compose -f docker/docker-compose.yml logs --tail=200 mongodb
docker compose -f docker/docker-compose.yml logs --tail=200 qdrant
docker compose -f docker/docker-compose.yml logs --tail=200 redis
```

- **API won't connect to DB**: Verify `.env` files have correct values and service names match `docker-compose.yml`
- **spaCy or torch fails during build**: Re-run with more resources or pin versions that have pre-built wheels
- **Services won't start**: Check container logs; database startup may need time before API connects

---

## Security & Cleanup

- The provided example envs are for **local testing only**—rotate or remove secrets before sharing code
- To remove all containers and named volumes for a clean start:

```bash
docker compose -f docker/docker-compose.yml down -v --remove-orphans
```

---

## Notes

If you want, I can:

- add small healthchecks to the `docker-compose.yml` for mongodb/qdrant/redis;
- add a simple `wait-for` script in the API image to block startup until DBs are reachable;
- run a local `docker compose up --build` here and report build logs (if you permit running commands).
