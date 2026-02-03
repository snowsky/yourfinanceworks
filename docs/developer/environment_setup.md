# Environment Variable Setup Guide

This guide explains how environment variables are loaded in different deployment scenarios.

## Overview

The application **no longer uses `load_dotenv()`** in Python code. Instead, environment variables are injected by the container runtime or shell environment. This approach ensures compatibility with:

- ✅ **Docker Compose** - via `env_file` directive
- ✅ **Kubernetes** - via ConfigMaps and Secrets
- ✅ **Local Development** - via shell export or IDE configuration

## Docker Compose (Recommended for Development)

### How It Works

The `docker-compose.yml` file uses the `env_file` directive to load environment variables from `./api/.env`:

```yaml
api:
  env_file:
    - ./api/.env
  environment:
    - DATABASE_URL=postgresql://...
```

**Important**: The `env_file` directive reads the `.env` file from the **host** and injects variables as environment variables into the container. It does **not** copy the file into the container.

### Setup

1. Create or update `api/.env` with your configuration:

   ```bash
   cp api/.env.example.full api/.env
   # Edit api/.env with your settings
   ```

2. Start services:

   ```bash
   docker-compose up -d
   ```

3. Verify environment variables are loaded:
   ```bash
   docker-compose exec api env | grep DATABASE_URL
   ```

## Kubernetes (Production)

### How It Works

Kubernetes injects environment variables directly into containers via:

1. **ConfigMaps** (non-sensitive configuration)
2. **Secrets** (sensitive data like API keys)

### Example ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: invoice-app-config
data:
  DATABASE_URL: "postgresql://postgres:password@postgres:5432/invoice_master"
  LOG_LEVEL: "INFO"
  KAFKA_BOOTSTRAP_SERVERS: "kafka:9092"
```

### Example Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: invoice-app-secrets
type: Opaque
stringData:
  SECRET_KEY: "your-super-secret-key"
  GOOGLE_CLIENT_SECRET: "your-oauth-secret"
```

### Example Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: invoice-app-api
spec:
  template:
    spec:
      containers:
        - name: api
          image: invoice-app:latest
          envFrom:
            - configMapRef:
                name: invoice-app-config
            - secretRef:
                name: invoice-app-secrets
          # Or individual env vars:
          env:
            - name: DATABASE_URL
              valueFrom:
                configMapKeyRef:
                  name: invoice-app-config
                  key: DATABASE_URL
```

## Local Development (Without Docker)

### Option 1: Export from .env File

```bash
cd api
export $(cat .env | xargs)
python main.py
```

### Option 2: Use direnv (Recommended)

1. Install direnv:

   ```bash
   # macOS
   brew install direnv

   # Add to ~/.zshrc or ~/.bashrc
   eval "$(direnv hook zsh)"
   ```

2. Create `.envrc` in project root:

   ```bash
   dotenv api/.env
   ```

3. Allow direnv:
   ```bash
   direnv allow
   ```

Now environment variables are automatically loaded when you `cd` into the project.

### Option 3: IDE Configuration

#### VS Code

Add to `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload"],
      "cwd": "${workspaceFolder}/api",
      "envFile": "${workspaceFolder}/api/.env"
    }
  ]
}
```

#### PyCharm

1. Go to Run → Edit Configurations
2. Select your run configuration
3. Under "Environment variables", click the folder icon
4. Click "Load from file" and select `api/.env`

## Running Scripts Locally

Scripts in `api/scripts/` no longer call `load_dotenv()`. To run them locally:

```bash
cd api
export $(cat .env | xargs)
python scripts/check_alembic_version.py
```

Or use a one-liner:

```bash
cd api && export $(cat .env | xargs) && python scripts/check_alembic_version.py
```

## Verification

### Check if Environment Variables are Loaded

**Docker Compose:**

```bash
docker-compose exec api python -c "import os; print('DB:', os.getenv('DATABASE_URL'))"
```

**Kubernetes:**

```bash
kubectl exec -it <pod-name> -- python -c "import os; print('DB:', os.getenv('DATABASE_URL'))"
```

**Local:**

```bash
python -c "import os; print('DB:', os.getenv('DATABASE_URL'))"
```

## Troubleshooting

### Environment Variables Not Loading in Docker Compose

1. Check that `env_file` is specified in `docker-compose.yml`
2. Verify the `.env` file exists at `./api/.env`
3. Restart services: `docker-compose restart`
4. Check logs: `docker-compose logs api`

### Environment Variables Not Loading in Kubernetes

1. Verify ConfigMap/Secret exists:

   ```bash
   kubectl get configmap invoice-app-config
   kubectl get secret invoice-app-secrets
   ```

2. Check pod environment:

   ```bash
   kubectl exec -it <pod-name> -- env
   ```

3. Verify deployment references ConfigMap/Secret correctly

### Scripts Fail Locally

Make sure to export environment variables before running:

```bash
export $(cat api/.env | xargs)
```

Or use direnv for automatic loading.

## Migration from load_dotenv()

If you have custom scripts or code that still uses `load_dotenv()`:

1. **Remove the import:**

   ```python
   # Remove this:
   from dotenv import load_dotenv
   load_dotenv()
   ```

2. **Use os.getenv() directly:**

   ```python
   import os

   DATABASE_URL = os.getenv("DATABASE_URL")
   SECRET_KEY = os.getenv("SECRET_KEY", "default-value")
   ```

3. **For local development**, export variables as shown above.

## Best Practices

1. **Never commit `.env` files** - they contain secrets
2. **Use `.env.example`** to document required variables
3. **In K8s, use Secrets** for sensitive data
4. **In Docker Compose, use `env_file`** for convenience
5. **For CI/CD, inject env vars** via pipeline configuration
