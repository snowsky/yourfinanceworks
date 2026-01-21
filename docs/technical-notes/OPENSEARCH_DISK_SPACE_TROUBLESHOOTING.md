# OpenSearch Disk Space Troubleshooting

## Problem
OpenSearch enters read-only mode when disk usage exceeds the flood-stage watermark, blocking write operations.

Error example:
```
ERROR:core.services.search_service:Error indexing expense 5: TransportError(429, 'cluster_block_exception', 'index [tenant_1_expenses] blocked by: [TOO_MANY_REQUESTS/12/disk usage exceeded flood-stage watermark, index has read-only-allow-delete block];')
```

## Root Cause
- OpenSearch has hit its disk usage threshold (flood-stage watermark, default 95%)
- It's blocking write operations with a `TOO_MANY_REQUESTS` error to protect the cluster
- The index enters read-only mode with `read-only-allow-delete` block

## Solutions

### 1. Free Up Disk Space (Immediate)
```bash
docker system prune -a --volumes
```

### 2. Adjust OpenSearch Watermark Thresholds
Update `docker-compose.yml` to increase thresholds or give more space:

```yaml
opensearch:
  environment:
    - cluster.routing.allocation.disk.watermark.flood_stage=95%
    - cluster.routing.allocation.disk.watermark.high=90%
    - cluster.routing.allocation.disk.watermark.low=85%
```

Or increase volume size:
```yaml
opensearch:
  volumes:
    - opensearch_data:/usr/share/opensearch/data
    
volumes:
  opensearch_data:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
      o: size=50g  # Increase as needed
```

### 3. Remove Read-Only Block (After Freeing Space)
Once you've freed disk space, reset the index:

```bash
curl -X PUT "localhost:9200/tenant_1_expenses/_settings" \
  -H 'Content-Type: application/json' \
  -d '{"index.blocks.read_only_allow_delete": null}'
```

### 4. Check Disk Usage
Monitor OpenSearch disk allocation:

```bash
docker exec opensearch curl -s localhost:9200/_cat/allocation?v
```

Or check cluster health:
```bash
docker exec opensearch curl -s localhost:9200/_cluster/health?pretty
```

## Prevention
- Monitor disk usage regularly
- Set up alerts for disk space thresholds
- Implement data retention policies to clean old indices
- Consider using index lifecycle management (ILM) for automatic cleanup
