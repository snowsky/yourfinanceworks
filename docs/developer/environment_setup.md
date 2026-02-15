# Environment Variable Setup Guide

This guide explains how environment variables are loaded in different deployment scenarios.

## Overview

The environment variables are injected by the container runtime or shell environment. This approach ensures compatibility with:

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
   docker-compose up --build -d
   ```

3. Verify environment variables are loaded:
   ```bash
   docker-compose exec api env | grep DATABASE_URL
   ```

## Troubleshooting

### Environment Variables Not Loading in Docker Compose

1. Check that `env_file` is specified in `docker-compose.yml`
2. Verify the `.env` file exists at `./api/.env`
3. Restart services: `docker-compose restart`
4. Check logs: `docker-compose logs api`

## Best Practices

1. **Never commit `.env` files** - they contain secrets
2. **Use `.env.example`** to document required variables
3. **In K8s, use Secrets** for sensitive data
4. **In Docker Compose, use `env_file`** for convenience
5. **For CI/CD, inject env vars** via pipeline configuration
