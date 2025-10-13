# Stage 4: Async Rolling

## Overview

Stage 4 builds on Stage 3 by adding asynchronous concurrent dice rolling capabilities. This demonstrates parent/child span relationships and concurrent operations in distributed traces.

## What's New in Stage 4

### New Features
- **Async Rolling Endpoint:** `/roll-async?die={type}&times={count}` - Roll multiple dice concurrently
- **Concurrent Operations:** Uses `asyncio.gather()` to roll N dice in parallel
- **Parent/Child Span Tracing:** Each individual roll creates a child span that runs concurrently
- **Async Metrics:** New Prometheus metrics for async operations
- **Enhanced Frontend UI:** Checkbox for async rolling with batch size input

### Key Learning Objectives
- Understanding parent/child span relationships in distributed tracing
- Visualizing concurrent operations in trace waterfalls (overlapping spans)
- Performance benefits of async operations
- Metrics for tracking concurrent operations
- Async programming patterns with OpenTelemetry instrumentation

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Frontend      │─────→│  Dice Roller    │─────→│  Die Service    │
│   (FastAPI)     │      │   (FastAPI)     │      │   (FastAPI)     │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                  │
                                  │ /roll-async endpoint
                                  ↓
                         ┌─────────────────┐
                         │ Concurrent Rolls│
                         │  (asyncio)      │
                         │  • Roll 1       │
                         │  • Roll 2       │
                         │  • Roll 3       │
                         │  • ...          │
                         └─────────────────┘
```

## Endpoints

### Dice Roller Service

**Existing:**
- `GET /roll?die={type}` - Roll a single die (synchronous)

**New in Stage 4:**
- `GET /roll-async?die={type}&times={count}` - Roll multiple dice concurrently
  - Parameters:
    - `die`: Die type (fair, risky, etc.)
    - `times`: Number of dice to roll (1-20)
  - Response: `{"total": 42, "rolls": [5, 3, 6, ...], "count": 10}`

### Frontend Service

**New in Stage 4:**
- `GET /roll-async?die={type}&times={count}` - Frontend wrapper for async rolling
- Enhanced UI with async rolling checkbox and batch size input

## Instrumentation

### New Metrics

**Dice Roller Service:**
```python
# Counter: Total async rolls
async_rolls_total{die_type, result}

# Histogram: Batch size distribution
async_roll_batch_size

# Histogram: Time to complete async batches
async_roll_duration_seconds

# Gauge: Current async operations in progress
async_rolls_in_progress
```

**Frontend Service:**
```python
# Counter: Async roll requests from frontend
async_roll_requests_total{batch_size}
```

### Trace Structure

**Async Roll Trace:**
```
HTTP GET /roll-async (parent span)
├─ Query die service
└─ Async roll batch (concurrent child spans)
   ├─ async_roll_0 ─────┐
   ├─ async_roll_1 ───┐ │  (these overlap
   ├─ async_roll_2 ─┐ │ │   in time!)
   ├─ async_roll_3 ─┼─┼─┘
   └─ ...           └─┘
```

**Key Span Attributes:**
- Parent: `async.batch_size`, `async.total_result`
- Children: `async.roll_index`, `die.result`, `die.error`

### Logs

**New log events:**
- INFO: "Async roll batch started" (die_type, times)
- INFO: "Async roll completed" (for each individual roll with index)
- INFO: "Async roll batch completed" (total, rolls, duration)
- ERROR: "Async roll batch failed"

## Quick Start

### Prerequisites
1. Main observability stack must be running:
   ```bash
   cd /path/to/sandbox
   make stack
   ```

### Start Stage 4

```bash
cd specs/illustrative-python/stage4
docker compose up -d
```

Services will be available at:
- Frontend: http://localhost:8108
- Dice Roller API: http://localhost:8107
- Die Service: http://localhost:8106

### Test Async Rolling

**Via Frontend UI:**
1. Open http://localhost:8108
2. Check "Use Async Rolling"
3. Set number of rolls (e.g., 5)
4. Click "Roll"

**Via curl:**
```bash
# Single sync roll
curl "http://localhost:8107/roll?die=fair"

# Async batch of 10 rolls
curl "http://localhost:8107/roll-async?die=fair&times=10"
```

### Generate Traffic

```bash
cd traffic-gen
python generate_traffic.py
```

Configuration in script:
- `ASYNC_PROBABILITY = 0.3` - 30% of requests use async
- `MAX_ASYNC_ROLLS = 10` - Maximum batch size

### Performance Testing

Compare sync vs async performance:

```bash
cd traffic-gen
python test-async-performance.py
```

This script:
- Runs 10 sequential `/roll` calls
- Runs 1 `/roll-async?times=10` call
- Compares execution times
- Calculates speedup factor

**Expected output:**
```
Sequential Rolls: 5.234 seconds
Async Batch Roll: 1.156 seconds
Async rolling is 4.53x FASTER than sequential!
```

## Observability

### Metrics (Prometheus)

**Async roll rate:**
```promql
rate(async_rolls_total[1m])
```

**Batch size percentiles:**
```promql
histogram_quantile(0.95, rate(async_roll_batch_size_bucket[5m]))
```

**Performance comparison:**
```promql
# Sync roll duration
avg(rate(http_request_duration_seconds_sum{handler="/roll"}[5m]) 
  / rate(http_request_duration_seconds_count{handler="/roll"}[5m]))

# Async batch duration
avg(rate(async_roll_duration_seconds_sum[5m]) 
  / rate(async_roll_duration_seconds_count[5m]))
```

### Logs (Loki)

**Async roll logs:**
```logql
{container_name="dice-roller-stage4"} | json | message =~ "Async roll"
```

**Filter by batch size:**
```logql
{container_name="dice-roller-stage4"} | json | times >= 5
```

### Traces (Tempo)

**In Grafana Explore:**
1. Select Tempo datasource
2. Search by service name: `dice-roller`
3. Look for traces with span name containing "async"

**Key observation:**
- The trace waterfall will show **overlapping child spans**
- This proves concurrent execution!
- Compare with sync traces where spans are sequential

**Query examples:**
```
service.name="dice-roller" AND name="GET /roll-async"
```

## Grafana Dashboard

Import the Stage 4 dashboard from `grafana-dashboards/stage4-dashboard.json` (when available).

**New panels:**
- Async vs Sync Roll Rate
- Async Batch Size Distribution
- Async Rolls In Progress
- Performance Improvement Factor
- Trace visualization examples

## Stopping Services

```bash
docker compose down

# Remove volumes as well
docker compose down -v
```

## Troubleshooting

### Async traces not showing concurrent spans

**Check:**
1. Verify async endpoint is being called: `docker compose logs dice-roller`
2. Check batch size is > 1: Look for "times" parameter in logs
3. Verify trace export: `docker compose --project-directory ../../stack logs otel-collector`

### Performance improvement not as expected

**Possible causes:**
- Small batch sizes (< 5) may not show significant improvement
- Network latency vs processing time ratio
- Error rate affecting measurements

**Check:**
```bash
# View async roll metrics
curl http://localhost:8107/metrics | grep async_roll
```

### Frontend checkbox not working

**Check browser console for JavaScript errors**
```bash
docker compose logs frontend
```

## Files

```
stage4/
├── README.md                    # This file
├── QUICK-START.md               # Quick command reference
├── IMPLEMENTATION-SUMMARY.md    # What was built
├── docker-compose.yml           # Service definitions
├── dice-roller/
│   ├── Dockerfile
│   ├── main.py                  # Modified with /roll-async endpoint
│   └── pyproject.toml
├── frontend/
│   ├── Dockerfile
│   ├── main.py                  # Modified with async UI
│   └── pyproject.toml
├── die-service/                 # Unchanged from Stage 3
│   ├── Dockerfile
│   ├── main.py
│   ├── pyproject.toml
│   └── die_specifications.json
├── traffic-gen/
│   ├── generate_traffic.py     # Modified with async support
│   ├── test-async-performance.py  # NEW: Performance comparison
│   └── pyproject.toml
└── grafana-dashboards/
    └── DASHBOARD-SPEC.md        # Dashboard specification

## Next Steps

After completing Stage 4, proceed to:
- **Stage 5:** Database Backend - Add PostgreSQL for die specifications
- **Stage 6:** Usage Tracking - Selective log routing with Alloy

## References

- [overview.md](../overview.md) - Complete stage specifications
- [implementation-notes.md](../implementation-notes.md) - Implementation patterns
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [Python asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
