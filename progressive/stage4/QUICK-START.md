# Stage 4 Quick Start

## Prerequisites

Ensure the observability stack is running:
```bash
cd /path/to/sandbox
make stack
```

## Start Stage 4

```bash
cd specs/illustrative-python/stage4
docker compose up -d
```

## Access Services

- **Frontend UI:** http://localhost:8108
- **Dice Roller API:** http://localhost:8107
- **Die Service API:** http://localhost:8106
- **Grafana:** http://localhost:3000
- **Prometheus:** http://localhost:9090
- **Tempo:** http://localhost:3200

## Quick Tests

### Test Sync Roll
```bash
curl "http://localhost:8107/roll?die=fair"
# Response: {"roll": 4}
```

### Test Async Roll (NEW in Stage 4)
```bash
curl "http://localhost:8107/roll-async?die=fair&times=5"
# Response: {"total": 18, "rolls": [3, 5, 2, 6, 2], "count": 5}
```

### Test via Frontend
```bash
open http://localhost:8108
# Check "Use Async Rolling", set number of rolls, click "Roll"
```

## Generate Traffic

```bash
cd traffic-gen
python generate_traffic.py
```

## Performance Test

```bash
cd traffic-gen
python test-async-performance.py
```

Expected output: Shows async is ~3-5x faster than sequential

## View Observability Data

### Metrics (Prometheus)
```bash
open http://localhost:9090
# Query: async_rolls_total
# Query: async_roll_batch_size_bucket
```

### Logs (Grafana → Loki)
```bash
open http://localhost:3000
# Navigate to Explore → Loki
# Query: {container_name="dice-roller-stage4"} | json | message =~ "Async"
```

### Traces (Grafana → Tempo)
```bash
open http://localhost:3000
# Navigate to Explore → Tempo
# Search: service.name="dice-roller"
# Look for traces with /roll-async - you'll see overlapping child spans!
```

## Key Observations

### In Tempo Trace View:
1. Find an async roll trace
2. Expand the spans
3. **Notice:** Multiple `async_roll_N` child spans
4. **Key Feature:** These spans OVERLAP in time (concurrent execution!)
5. Compare with sync `/roll` traces where operations are sequential

### In Metrics:
```bash
# Compare async vs sync rates
curl http://localhost:8107/metrics | grep -E "(dice_rolls_total|async_rolls_total)"

# Check async performance
curl http://localhost:8107/metrics | grep async_roll_duration_seconds
```

## Stop Services

```bash
docker compose down

# Or remove volumes too
docker compose down -v
```

## Troubleshooting

### Services not starting
```bash
docker compose logs
```

### Check service health
```bash
docker compose ps
curl http://localhost:8107/
curl http://localhost:8108/
curl http://localhost:8106/
```

### View real-time logs
```bash
docker compose logs -f dice-roller
docker compose logs -f frontend
```

## Common Commands

```bash
# Restart a service
docker compose restart dice-roller

# Rebuild after code changes
docker compose up -d --build

# View metrics endpoint
curl http://localhost:8107/metrics

# Check Alloy is collecting logs
curl 'http://localhost:3100/loki/api/v1/query_range' \
  --get --data-urlencode 'query={container_name="dice-roller-stage4"}'
```

## Performance Test Interpretation

```
Sequential (10 rolls): ~5-6 seconds
  Each roll: 0.5-1s delay + processing
  Total: Delays add up sequentially

Async (10 rolls): ~1-1.5 seconds
  All rolls: Run concurrently
  Total: Dominated by longest single roll

Speedup: ~4-5x
```

## Next Steps

1. Generate traffic for a few minutes
2. Explore traces in Tempo (look for concurrent spans!)
3. Check Grafana dashboards
4. Run performance test multiple times
5. Compare async vs sync behavior in traces

## Resources

- Full README: [README.md](README.md)
- Implementation details: [IMPLEMENTATION-SUMMARY.md](IMPLEMENTATION-SUMMARY.md)
- Dashboard spec: [grafana-dashboards/DASHBOARD-SPEC.md](grafana-dashboards/DASHBOARD-SPEC.md)
