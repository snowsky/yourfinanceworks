# Invoice App Helm Chart

This Helm chart deploys the Invoice Application with API, UI, and PostgreSQL database components.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- NGINX Ingress Controller (for ingress functionality)

## Images to build

- `invoice-app-api:latest` built from `./api/Dockerfile`
- `invoice-app-ui:latest` built from `./ui/Dockerfile`
- `invoice-app-ocr:latest` built from `./api/Dockerfile` (same image as API, different command)

Build examples

```bash
# From repo root
docker build -t invoice-app-api:latest ./api
docker build -t invoice-app-ui:latest ./ui
docker build -t invoice-app-ocr:latest ./api

# If using a remote registry
docker tag invoice-app-api:latest <REGISTRY>/invoice-app-api:latest
docker tag invoice-app-ui:latest <REGISTRY>/invoice-app-ui:latest
docker tag invoice-app-ocr:latest <REGISTRY>/invoice-app-ocr:latest
docker push <REGISTRY>/invoice-app-api:latest
docker push <REGISTRY>/invoice-app-ui:latest
docker push <REGISTRY>/invoice-app-ocr:latest
```

## Installing the Chart

To install the chart with the release name `my-release`:

```bash
helm install my-release ./infra/helm/invoice-app
```

## Configuration

The following table lists the configurable parameters of the Invoice App chart and their default values.

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Namespace for all resources | `invoice-app` |
| `global.imagePullPolicy` | Image pull policy | `IfNotPresent` |

### PostgreSQL Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL dependency | `true` |
| `postgresql.auth.postgresPassword` | PostgreSQL admin password | `password` |
| `postgresql.auth.username` | PostgreSQL username | `postgres` |
| `postgresql.auth.password` | PostgreSQL user password | `password` |
| `postgresql.auth.database` | PostgreSQL database name | `invoice_master` |
| `postgresql.primary.persistence.size` | PostgreSQL PVC size | `5Gi` |

### API Service Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.enabled` | Enable API service | `true` |
| `api.image.repository` | API image repository | `invoice-app-api` |
| `api.image.tag` | API image tag | `latest` |
| `api.replicas` | Number of API replicas | `1` |
| `api.port` | API service port | `8000` |

### UI Service Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ui.enabled` | Enable UI service | `true` |
| `ui.image.repository` | UI image repository | `invoice-app-ui` |
| `ui.image.tag` | UI image tag | `latest` |
| `ui.replicas` | Number of UI replicas | `1` |
| `ui.port` | UI service port | `8080` |

### Ingress Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts[0].host` | Ingress host | `invoice-app.local` |

### Optional Components

| Parameter | Description | Default |
|-----------|-------------|---------|
| `kafka.enabled` | Enable Kafka | `false` |
| `ocrWorker.enabled` | Enable OCR Worker | `false` |
| `kafdrop.enabled` | Enable Kafdrop | `false` |

## Example Configuration

```yaml
# values.yaml
global:
  namespace: my-invoice-app

postgresql:
  auth:
    postgresPassword: "my-secret-password"

ingress:
  hosts:
    - host: invoice.mycompany.com

api:
  image:
    tag: "v1.2.3"

ui:
  image:
    tag: "v1.2.3"
```

## Components

This chart includes the following components:

1. **API Service**: FastAPI-based backend service
2. **UI Service**: React-based frontend service
3. **PostgreSQL**: Database with multi-tenant support
4. **Ingress**: NGINX ingress for external access
5. **Optional Kafka**: Message queue (disabled by default)
6. **Optional OCR Worker**: Document processing worker (disabled by default)
7. **Optional Kafdrop**: Kafka UI (disabled by default)

## Database Initialization

The PostgreSQL database is automatically initialized with the required schema for multi-tenant support. The initialization script creates:

- Master database with tenant management tables
- User authentication tables
- Required extensions (UUID-OSSP)

## Secrets Management

API secrets are managed through Kubernetes secrets. Configure the following in your values:

```yaml
api:
  secrets:
    GOOGLE_CLIENT_ID: "your-google-client-id"
    GOOGLE_CLIENT_SECRET: "your-google-client-secret"
    SLACK_VERIFICATION_TOKEN: "your-slack-token"
    # ... other secrets
```

## Upgrading

To upgrade the chart:

```bash
helm upgrade my-release ./infra/helm/invoice-app
```

## Uninstalling

To uninstall the chart:

```bash
helm uninstall my-release
```

## Troubleshooting

1. Check pod status: `kubectl get pods -n invoice-app`
2. Check logs: `kubectl logs -n invoice-app deployment/api`
3. Verify ingress: `kubectl get ingress -n invoice-app`
4. Check PostgreSQL: `kubectl exec -it -n invoice-app statefulset/postgres-master -- psql -U postgres -d invoice_master`