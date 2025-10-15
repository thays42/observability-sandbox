# Dashboard Fix Applied ✅

## Issue
The async metrics panels in the Stage 4 Grafana dashboard were showing "No data" despite metrics being collected.

## Root Cause
The dashboard queries were using the wrong label selector:
- **Incorrect:** `container_name="dice-roller-stage4"`
- **Correct:** `job="dice-roller-stage4"`

### Explanation
- Prometheus metrics are scraped from service endpoints with labels like `job` and `instance`
- The `container_name` label is used by Loki for logs, not by Prometheus for metrics
- When Prometheus scrapes metrics, it applies labels from the scrape configuration (job name)

## Fix Applied

Updated all async metrics queries in `stage4-dashboard.json`:

```bash
# Changed from:
async_rolls_total{container_name="dice-roller-stage4"}

# To:
async_rolls_total{job="dice-roller-stage4"}
```

## Affected Panels

### Async Roll Metrics Row
1. **Async vs Sync Roll Rate** - ✅ Fixed
   - Query A: `rate(dice_rolls_total{job="dice-roller-stage4"}[1m])`
   - Query B: `rate(async_rolls_total{job="dice-roller-stage4"}[1m])`

2. **Async Batch Size Distribution** - ✅ Fixed
   - Query A: `histogram_quantile(0.50, rate(async_roll_batch_size_bucket{job="dice-roller-stage4"}[5m]))`
   - Query B: `histogram_quantile(0.95, rate(async_roll_batch_size_bucket{job="dice-roller-stage4"}[5m]))`
   - Query C: `histogram_quantile(0.99, rate(async_roll_batch_size_bucket{job="dice-roller-stage4"}[5m]))`

3. **Async Rolls In Progress** - ✅ Fixed
   - Query: `async_rolls_in_progress{job="dice-roller-stage4"}`

4. **Total Async Rolls** - ✅ Fixed
   - Query: `sum(async_rolls_total{job="dice-roller-stage4"})`

### Async Performance Comparison Row
1. **Sync Roll Avg Duration** - ✅ Fixed
   - Query: `avg(rate(http_request_duration_seconds_sum{handler="/roll",job="dice-roller-stage4"}[5m]) / rate(http_request_duration_seconds_count{handler="/roll",job="dice-roller-stage4"}[5m]))`

2. **Async Batch Avg Duration** - ✅ Fixed
   - Query: `avg(rate(async_roll_duration_seconds_sum{job="dice-roller-stage4"}[5m]) / rate(async_roll_duration_seconds_count{job="dice-roller-stage4"}[5m]))`

3. **Speedup Factor** - ✅ Fixed
   - Query: Ratio of sync to async duration (both using `job="dice-roller-stage4"`)

## Verification

### Test Queries in Prometheus
```bash
# Basic metric check
curl --data-urlencode 'query=async_rolls_total{job="dice-roller-stage4"}' \
  http://localhost:9090/api/v1/query

# Rate query
curl --data-urlencode 'query=rate(async_rolls_total{job="dice-roller-stage4"}[1m])' \
  http://localhost:9090/api/v1/query
```

### Current Metric Values
As of fix:
- `async_rolls_total{die_type="fair"}`: 69 rolls
- `async_rolls_total{die_type="risky"}`: 94 rolls (87 success + 7 errors)
- `async_roll_batch_size_sum`: 170 (30 batches)
- Average batch size: ~5.67 dice per batch

## What You Should See Now

After opening the dashboard at http://localhost:3000:

1. **Async vs Sync Roll Rate**
   - Two lines showing roll rates over time
   - Should have data if any rolls have been made

2. **Async Batch Size Distribution**
   - P50, P95, P99 lines
   - Shows distribution of batch sizes (1-20)

3. **Async Rolls In Progress**
   - Gauge showing 0 when idle
   - Spikes when async requests are active

4. **Total Async Rolls**
   - Should show 170 (or current total)

5. **Performance Comparison**
   - Sync duration: ~0.5-1 second average
   - Async duration: ~0.5-1 second average
   - Speedup: ~1-5x depending on batch size

## Testing the Dashboard

### Generate Data
```bash
# Make some async requests
for i in {1..5}; do
  curl "http://localhost:8107/roll-async?die=fair&times=5"
  sleep 1
done

# Refresh Grafana dashboard (wait ~15 seconds for scrape)
```

### Run Traffic Generation
```bash
cd /Users/thays/Projects/observability/sandbox/specs/illustrative-python/stage4/traffic-gen
source .venv/bin/activate
python generate_traffic.py
```

This will generate mixed sync and async traffic, populating all dashboard panels.

## Grafana Dashboard Refresh

The dashboard configuration is reloaded automatically. If panels still show "No data":

1. **Wait 15-30 seconds** - Prometheus scrapes every 15 seconds
2. **Check time range** - Ensure dashboard time range includes recent data
3. **Verify services** - Make sure stage4 services are running:
   ```bash
   docker compose --project-directory /Users/thays/Projects/observability/sandbox/specs/illustrative-python/stage4 ps
   ```
4. **Hard refresh** - Click the refresh button in Grafana or press Ctrl+Shift+R

## Files Modified

- `/stack/grafana/provisioning/dashboards/files/stage4-dashboard.json`
  - All async metric queries updated to use `job="dice-roller-stage4"`
  - Backup created: `stage4-dashboard.json.backup`

## Lessons Learned

1. **Prometheus vs Loki labels are different**
   - Prometheus: `job`, `instance`, `handler`, etc.
   - Loki: `container_name`, `compose_project`, `compose_service`, etc.

2. **Always verify label availability**
   - Check what labels exist: `curl http://localhost:9090/api/v1/query?query=your_metric`
   - Don't assume labels from one system exist in another

3. **Grafana queries need proper labels**
   - Use the correct label selectors for the data source
   - Metrics (Prometheus) and logs (Loki) have different labeling schemes

## Status
✅ **FIXED** - All async metrics panels should now display data

---

**Fixed:** 2025-10-12  
**Issue:** Wrong label selector in queries  
**Solution:** Changed from `container_name` to `job` label
