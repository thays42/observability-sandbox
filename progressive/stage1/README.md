# Stage 1: Single FastAPI Service

## Overview

Stage 1 establishes the observability foundation with a single FastAPI service that provides a dice rolling API. This stage demonstrates:

- **Metrics**: Automatic HTTP metrics + custom business metrics
- **Logs**: Structured JSON logging with trace context
- **Traces**: OpenTelemetry automatic instrumentation
- **Dashboards**: 12-panel Grafana dashboard

## Architecture

```
┌─────────────────┐
│  Dice Roller    │──→ Prometheus (metrics)
│   (FastAPI)     │──→ Loki via Alloy (logs)
│   Port 8100     │──→ Tempo via OTel Collector (traces)
└─────────────────┘
```

## Service Specification

### Dice Roller API

**Endpoint**: `GET /roll?die={type}`

**Parameters**:
- `die` (required): Either "fair" or "risky"

**Behavior**:
- **fair**: Standard 6-sided die (rolls 1-6)
- **risky**: Adds 1 to each roll (rolls 2-7), 10% chance of 500 error
- Random delay up to 1 second on all rolls

**Response**: `{"roll": <value>}`

## Prerequisites

1. Main observability stack must be running:
   ```bash
   cd /Users/thays/Projects/observability/sandbox
   make stack
   ```

2. Python 3.13+ with uv installed:
   ```bash
   # Install uv if needed
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

## Quick Start

### 1. Start the Service

```bash
cd specs/illustrative-python/stage1
docker compose up -d --build
```

### 2. Verify Service is Running

```bash
# Check service health
curl http://localhost:8100/

# Make a test roll
curl "http://localhost:8100/roll?die=fair"

# Check metrics endpoint
curl http://localhost:8100/metrics
```

### 3. Restart Stack Services to Pick Up Config Changes

```bash
cd /Users/thays/Projects/observability/sandbox
docker compose --project-directory stack restart alloy
docker compose --project-directory stack restart prometheus
docker compose --project-directory stack restart grafana
```

### 4. Generate Traffic

```bash
cd specs/illustrative-python/stage1/traffic-gen

# Install dependencies
uv pip install -r pyproject.toml

# Run traffic generation
python generate_traffic.py
```

### 5. View Dashboard

1. Navigate to http://localhost:3000 (Grafana)
2. Go to **Dashboards** → **Dice Roller - Stage 1**
3. You should see data populating all 12 panels

## Instrumentation Details

### Metrics

**Automatic** (via `prometheus-fastapi-instrumentator`):
- `http_requests_total` - Total HTTP requests by method, handler, status
- `http_request_duration_seconds` - Request duration histogram

**Custom** (business metrics):
- `dice_rolls_total{die_type, result}` - Counter of rolls by type and result
- `dice_roll_value{die_type}` - Histogram of roll values (buckets: 1-8)

**Endpoint**: http://localhost:8100/metrics

### Logs

**Format**: Structured JSON to stdout

**Fields**:
- `timestamp`: ISO 8601 format
- `level`: INFO, WARNING, ERROR
- `message`: Human-readable message
- `logger`: Logger name
- `trace_id`: OpenTelemetry trace ID (32-char hex)
- `span_id`: OpenTelemetry span ID (16-char hex)
- `die_type`: "fair" or "risky" (for roll events)
- `roll_value`: The actual roll result (for roll events)

**Example**:
```json
{
  "timestamp": "2025-10-12T10:30:00.123456Z",
  "level": "INFO",
  "message": "Roll completed",
  "logger": "__main__",
  "trace_id": "0123456789abcdef0123456789abcdef",
  "span_id": "0123456789abcdef",
  "die_type": "fair",
  "roll_value": 5
}
```

**Collection**: Logs collected by Grafana Alloy and sent to Loki

### Traces

**Framework**: OpenTelemetry with automatic FastAPI instrumentation

**Exporter**: OTLP HTTP to `alloy:4318`

**Service Name**: `dice-roller`

**Spans**:
- Automatic span for each HTTP request
- Custom attributes: `die.type`, `die.result`, `die.error`

**Viewing**: Navigate to Grafana → Explore → Tempo → Search by service name `dice-roller`

## Dashboard Panels

The Grafana dashboard includes 12 panels organized in 5 rows:

### Row 1: Overview Metrics
1. **Request Rate** - Requests per second graph
2. **Success Rate** - Gauge showing % of successful requests (< 500 status)
3. **Error Rate by Die Type** - Errors per second by die type

### Row 2: Latency Metrics
4. **Request Duration** - P50, P95, P99 latency percentiles
5. **Average Response Time by Die Type** - Bar chart comparing fair vs risky

### Row 3: Roll Distribution
6. **Rolls by Die Type** - Pie chart of fair vs risky usage
7. **Roll Value Distribution (Fair)** - Histogram of fair die results (1-6)
8. **Roll Value Distribution (Risky)** - Histogram of risky die results (2-7)

### Row 4: Logs and Traces
9. **Recent Logs** - Log stream from Loki
10. **Error Logs** - Filtered to ERROR level only
11. **Trace-to-Logs Correlation Instructions** - Text panel with instructions
12. **Trace Count** - Stat showing recent trace count

## Testing Checklist

### ✅ Service Health

- [ ] Service starts without errors: `docker compose ps`
- [ ] Root endpoint responds: `curl http://localhost:8100/`
- [ ] Metrics endpoint accessible: `curl http://localhost:8100/metrics`
- [ ] Fair die roll works: `curl "http://localhost:8100/roll?die=fair"`
- [ ] Risky die roll works (may error): `curl "http://localhost:8100/roll?die=risky"`

### ✅ Metrics Collection

- [ ] Prometheus scraping stage1: http://localhost:9090/targets (check `dice-roller-stage1` is UP)
- [ ] HTTP metrics present: Query `http_requests_total{job="dice-roller-stage1"}` in Prometheus
- [ ] Custom metrics present: Query `dice_rolls_total` in Prometheus
- [ ] Roll value histogram present: Query `dice_roll_value_bucket` in Prometheus

### ✅ Log Collection

- [ ] Alloy discovering container: http://localhost:12345 (check for `dice-roller-stage1` in targets)
- [ ] Logs in Loki: 
  ```bash
  curl 'http://localhost:3100/loki/api/v1/query_range' \
    --get --data-urlencode 'query={container_name="dice-roller-stage1"}'
  ```
- [ ] Logs include trace_id: Check log output includes `trace_id` field
- [ ] Logs include span_id: Check log output includes `span_id` field
- [ ] JSON parsing works: Loki query `{container_name="dice-roller-stage1"} | json` shows parsed fields

### ✅ Trace Collection

- [ ] Traces in Tempo: Grafana → Explore → Tempo → Search by `service.name="dice-roller"`
- [ ] Traces show up within seconds of requests
- [ ] Trace includes custom attributes: Click trace → See `die.type`, `die.result` attributes
- [ ] Trace duration matches request time (includes sleep delay)

### ✅ Trace-to-Logs Correlation

- [ ] Open a trace in Tempo
- [ ] Click on a span
- [ ] Click "Logs for this span" button
- [ ] Verify it jumps to Loki with correct trace_id filter
- [ ] Verify logs with matching trace_id appear

### ✅ Dashboard

- [ ] Dashboard appears in Grafana: Dashboards → "Dice Roller - Stage 1"
- [ ] All 12 panels load without errors
- [ ] Request rate panel shows data after traffic generation
- [ ] Success rate gauge shows ~90% (due to 10% risky errors)
- [ ] Error rate panel shows risky die errors
- [ ] Latency panels show distribution with ~0.5s average (due to random sleep)
- [ ] Pie chart shows fair vs risky distribution
- [ ] Histograms show correct roll value ranges (1-6 for fair, 2-7 for risky)
- [ ] Log panels show recent and error logs
- [ ] Trace count shows > 0 traces

### ✅ Traffic Generation

- [ ] Traffic script installs dependencies: `cd traffic-gen && uv pip install -r pyproject.toml`
- [ ] Script runs successfully: `python generate_traffic.py`
- [ ] Script logs user activity: Check for "User X roll Y" messages
- [ ] Script completes: Check for "Traffic generation complete" message
- [ ] Script handles errors gracefully: Risky die errors don't crash script

## Troubleshooting

### Service won't start

```bash
# Check logs
docker compose logs dice-roller

# Common issues:
# - Port 8100 already in use (check with: lsof -i :8100)
# - Missing monitoring network (create with: docker network create monitoring)
# - OTel Collector not running (check stack: make stack)
```

### Metrics not appearing in Prometheus

```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Check if dice-roller-stage1 is in the list and UP
# If not, restart Prometheus to pick up config changes
docker compose --project-directory stack restart prometheus

# Wait 15 seconds for scrape interval
```

### Logs not appearing in Loki

```bash
# Check Alloy is discovering the container
open http://localhost:12345

# Check for dice-roller-stage1 in discovered targets
# If not present, check Alloy config includes stage1-dice-roller project
cat stack/alloy/config.alloy | grep stage1

# Restart Alloy to pick up config changes
docker compose --project-directory stack restart alloy
```

### Traces not appearing in Tempo

```bash
# Check OTel Collector is running
docker compose --project-directory stack logs otel-collector

# Check dice-roller can reach OTel Collector
docker exec dice-roller-stage1 curl -v http://alloy:4318/v1/traces

# Verify OTEL environment variables are set
docker exec dice-roller-stage1 env | grep OTEL
```

### Dashboard not loading

```bash
# Restart Grafana to pick up dashboard
docker compose --project-directory stack restart grafana

# Check dashboard file exists
ls -la grafana-dashboards/

# Manually import dashboard:
# 1. Navigate to http://localhost:3000
# 2. Dashboards → New → Import
# 3. Upload stage1-dashboard.json
```

## Stopping the Service

```bash
# Stop and remove containers
docker compose down

# Stop and remove containers + volumes (clean slate)
docker compose down -v
```

## Next Steps

Once Stage 1 is working:

1. Verify all checklist items pass ✅
2. Experiment with the dashboard - try different time ranges, queries
3. Practice trace-to-logs correlation workflow
4. Understand the data flow: app → metrics/logs/traces → observability stack → Grafana
5. Ready for **Stage 2**: Adding a Streamlit frontend with distributed tracing

## Configuration Files

- **Application**: `dice-roller/main.py` - FastAPI app with instrumentation
- **Dependencies**: `dice-roller/pyproject.toml` - Python packages
- **Container**: `dice-roller/Dockerfile` - Docker image definition
- **Compose**: `docker-compose.yml` - Service definition with environment variables
- **Traffic**: `traffic-gen/generate_traffic.py` - Async traffic generator
- **Dashboard**: `grafana-dashboards/stage1-dashboard.json` - Grafana dashboard definition

## Key Learning Points

1. **Automatic instrumentation** - OpenTelemetry can instrument FastAPI with minimal code
2. **Trace context propagation** - trace_id and span_id automatically injected into logs
3. **Custom metrics** - Business-specific metrics complement automatic HTTP metrics
4. **Histogram buckets** - Choosing appropriate buckets for roll values (1-8)
5. **Trace-to-logs correlation** - The power of unified observability (traces → logs)
6. **Labels matter** - Proper labeling (die_type, result) enables detailed queries
7. **JSON structured logging** - Makes logs queryable and parseable
8. **Grafana datasources** - Single dashboard can query Prometheus, Loki, and Tempo
