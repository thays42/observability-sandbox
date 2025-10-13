# Stage 4 Grafana Dashboard Specification

## Overview
The Stage 4 dashboard extends Stage 3 with additional panels for async rolling metrics.

## Base Configuration
- **Title:** Dice Roller - Stage 4 (Async Rolling)
- **UID:** stage4-dice-roller
- **Tags:** stage4, dice-roller, async, observability-demo
- **Refresh:** 5s
- **Time range:** Last 1 hour

## Dashboard Structure

### Row 1: Overview (from Stage 3)
Same as Stage 3 - service status and general information

### Row 2: HTTP Metrics - Dice Roller (from Stage 3)
Same as Stage 3:
- Request Rate
- Error Rate
- P50/P95/P99 Latency
- Status Code Distribution

### Row 3: HTTP Metrics - Frontend (from Stage 3)
Same as Stage 3:
- Request Rate
- Backend Request Duration
- Frontend Error Rate

### Row 4: HTTP Metrics - Die Service (from Stage 3)
Same as Stage 3:
- Request Rate
- Response Time
- Die Requests by Type

### Row 5: **NEW - Async Roll Metrics** ⭐

#### Panel 1: Async vs Sync Roll Rate
- **Type:** Time series (Graph)
- **Queries:**
  ```promql
  # Sync rolls (individual)
  rate(dice_rolls_total[1m])
  
  # Async rolls (individual, from batches)
  rate(async_rolls_total[1m])
  ```
- **Legend:** 
  - "Sync Rolls/sec"
  - "Async Rolls/sec (from batches)"

#### Panel 2: Async Batch Size Distribution
- **Type:** Time series (Graph)
- **Queries:**
  ```promql
  # P50 batch size
  histogram_quantile(0.50, rate(async_roll_batch_size_bucket[5m]))
  
  # P95 batch size
  histogram_quantile(0.95, rate(async_roll_batch_size_bucket[5m]))
  
  # P99 batch size
  histogram_quantile(0.99, rate(async_roll_batch_size_bucket[5m]))
  ```
- **Legend:** "P50", "P95", "P99"

#### Panel 3: Async Rolls In Progress
- **Type:** Gauge
- **Query:**
  ```promql
  async_rolls_in_progress
  ```
- **Thresholds:** 
  - Green: 0-5
  - Yellow: 5-10
  - Red: >10

#### Panel 4: Total Async Roll Requests
- **Type:** Stat
- **Query:**
  ```promql
  sum(async_rolls_total)
  ```

### Row 6: **NEW - Async Performance Comparison** ⭐

#### Panel 1: Sync Roll Average Duration
- **Type:** Stat
- **Query:**
  ```promql
  avg(rate(http_request_duration_seconds_sum{handler="/roll"}[5m]) 
    / rate(http_request_duration_seconds_count{handler="/roll"}[5m]))
  ```
- **Unit:** seconds
- **Decimals:** 3

#### Panel 2: Async Roll Average Duration  
- **Type:** Stat
- **Query:**
  ```promql
  avg(rate(async_roll_duration_seconds_sum[5m]) 
    / rate(async_roll_duration_seconds_count[5m]))
  ```
- **Unit:** seconds
- **Decimals:** 3

#### Panel 3: Performance Improvement Factor
- **Type:** Stat
- **Query (calculated):**
  ```promql
  avg(rate(http_request_duration_seconds_sum{handler="/roll"}[5m]) 
    / rate(http_request_duration_seconds_count{handler="/roll"}[5m]))
  /
  avg(rate(async_roll_duration_seconds_sum[5m]) 
    / rate(async_roll_duration_seconds_count[5m]))
  ```
- **Unit:** none (ratio)
- **Decimals:** 2
- **Prefix:** "×"
- **Color:** Green if > 1

#### Panel 4: Async Duration Distribution
- **Type:** Heatmap
- **Query:**
  ```promql
  rate(async_roll_duration_seconds_bucket[1m])
  ```

### Row 7: Business Metrics (from Stage 3)
Same as Stage 3:
- Roll Value Distribution
- Die Type Usage
- Success Rate

### Row 8: Service-to-Service Metrics (from Stage 3)
Same as Stage 3:
- Die Service Request Rate
- Die Service Duration

### Row 9: **UPDATED - Distributed Traces** ⭐

#### Panel 1: Trace Instructions (Text)
**Updated content:**
```
Use Grafana Explore → Tempo to view distributed traces:

1. Sync traces: 4 services (traffic-gen → frontend → dice-roller → die-service)
2. Async traces: Look for traces with CONCURRENT CHILD SPANS
   - Search: service.name="dice-roller" AND span.name contains "async"
   - The trace waterfall shows OVERLAPPING spans (parallel execution)
   - Parent span: /roll-async endpoint
   - Child spans: individual async_roll_N operations running concurrently

Example queries:
- All async traces: {service.name="dice-roller"} | json | span_name =~ "async_roll_.*"
- High batch sizes: {service.name="dice-roller"} | json | async.batch_size > 5
```

#### Panel 2: Recent Trace IDs (Logs)
**Query (Loki):**
```logql
{container_name="dice-roller-stage4"} | json | message =~ "Async roll batch"
```

### Row 10: **NEW - Async Trace Visualization** ⭐

#### Panel 1: Understanding Concurrent Spans (Text)
```markdown
## Concurrent Span Visualization

In async traces, you'll see:

1. **Parent Span:** The /roll-async HTTP request
   - Duration = total time from request start to response
   - Contains metadata: die type, batch size, total result

2. **Child Spans:** Individual async roll operations
   - Each roll creates its own span: async_roll_0, async_roll_1, etc.
   - **Key Feature:** These spans OVERLAP in time (run concurrently)
   - Each contains: roll index, die type, individual result

**Visual Pattern in Tempo:**
```
Parent Span:    [====================]
  Child 0:      [======]
  Child 1:        [=====]
  Child 2:       [======]
  Child 3:         [=====]
  ...
```

The overlapping child spans prove concurrent execution!
```

### Row 11: Logs (from Stage 3)
Same as Stage 3:
- Recent logs from all services
- Error logs

### Row 12: System Metrics (from Stage 3)
Same as Stage 3 (if included):
- Container CPU
- Container Memory

## Implementation Notes

To create the actual dashboard:
1. Copy stage3-dashboard.json
2. Update dashboard metadata (title, UID, tags)
3. Update all prometheus queries to reference stage4 container labels
4. Add the 3 new rows (5, 6, 10) with panels as specified above
5. Update row 9 with new trace instructions
6. Save to `stage4-dashboard.json`

Alternatively, after services are running:
1. Import stage3 dashboard in Grafana
2. Manually add new panels via UI
3. Export as JSON to `stage4-dashboard.json`
