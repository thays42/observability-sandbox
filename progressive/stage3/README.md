# Stage 3: Three-Service Architecture with Die Service

## Overview

Stage 3 introduces a third service (**Die Service**) that provides die specifications, creating a three-tier architecture:

```
Frontend → Dice Roller → Die Service
```

This demonstrates:
- Multi-hop distributed tracing across 3 services
- Service-to-service communication patterns
- Dynamic configuration loading from a backend service
- Service dependency management

## Architecture

### Services

1. **Frontend** (port 8105)
   - Serves HTML UI with dynamically populated die types
   - Fetches available die types from Die Service on startup
   - Forwards roll requests to Dice Roller
   - Propagates trace context

2. **Dice Roller** (port 8104)
   - Queries Die Service for die specifications
   - Uses specifications (faces, error_rate) to perform rolls
   - Adds service-to-service metrics
   - Propagates trace context to Die Service

3. **Die Service** (port 8103)
   - Provides die specifications via JSON API
   - `GET /dice` → list of available die identifiers
   - `GET /dice?identifier=X` → specific die specification
   - Loads specifications from JSON file at startup

### Data Flow

1. User clicks "Roll" in Frontend UI
2. Frontend calls `Dice Roller: GET /roll?die=fair`
3. Dice Roller calls `Die Service: GET /dice?identifier=fair`
4. Die Service returns `{"faces": [1,2,3,4,5,6], "error_rate": 0}`
5. Dice Roller uses specification to perform roll
6. Result propagates back: Dice Roller → Frontend → User

**Trace spans created:**
- Frontend HTTP request span
- Frontend → Dice Roller HTTP client span
- Dice Roller HTTP request span
- Dice Roller → Die Service HTTP client span
- Die Service HTTP request span

## Getting Started

### Prerequisites

1. Main observability stack must be running:
   ```bash
   cd /Users/thays/Projects/observability/sandbox
   make stack
   ```

2. Verify Prometheus, Loki, Tempo, and OTel Collector are healthy:
   ```bash
   docker compose --project-directory stack ps
   ```

### Starting Stage 3

```bash
cd specs/illustrative-python/stage3
docker compose up -d
```

### Verify Services

```bash
# Check all services are running
docker compose ps

# Check die service
curl http://localhost:8103/
curl http://localhost:8103/dice
curl http://localhost:8103/dice?identifier=fair

# Check dice roller
curl http://localhost:8104/
curl "http://localhost:8104/roll?die=fair"

# Check frontend
curl http://localhost:8105/
open http://localhost:8105  # Opens UI in browser
```

### View Metrics

```bash
# Die Service metrics
curl http://localhost:8103/metrics

# Dice Roller metrics
curl http://localhost:8104/metrics

# Frontend metrics
curl http://localhost:8105/metrics
```

## New Instrumentation in Stage 3

### Die Service Metrics

**Custom Prometheus metrics:**
- `die_specifications_requested_total{identifier}` - Counter of requests by identifier
- `die_list_requests_total` - Counter of list requests
- `die_specifications_loaded` - Gauge of loaded specifications count

### Dice Roller - New Metrics

**Service-to-service metrics:**
- `die_service_requests_total{identifier, status}` - Counter of die service calls
- `die_service_request_duration_seconds` - Histogram of die service call duration

### Distributed Tracing

All services automatically create spans for:
- HTTP requests (incoming)
- HTTP requests (outgoing)
- Trace context propagation via W3C Trace Context headers

**View traces in Grafana:**
1. Navigate to http://localhost:3000 → Explore
2. Select Tempo datasource
3. Search by `service.name="frontend"` or `service.name="dice-roller"`
4. View trace waterfall showing all 3 services

## Traffic Generation

Generate test traffic:

```bash
cd traffic-gen

# Install dependencies
uv pip install -r pyproject.toml

# Run traffic generator
python generate_traffic.py
```

**Configuration:**
- `NUM_USERS = 10` - Number of concurrent users
- `MAX_ROLLS_PER_USER = 20` - Maximum rolls per user

The script:
- Simulates realistic user behavior
- Creates distributed traces across all 3 services
- Randomly selects die types (fair/risky)
- Adds random think time between requests
- Logs all activity

## Observability

### Metrics (Prometheus)

Access Prometheus at http://localhost:9090

**Key queries:**

```promql
# Die Service request rate
rate(http_requests_total{job="die-service-stage3"}[1m])

# Die specifications requested
sum by (identifier) (die_specifications_requested_total)

# Dice Roller → Die Service request rate
rate(die_service_requests_total[1m])

# Service-to-service latency (P95)
histogram_quantile(0.95, rate(die_service_request_duration_seconds_bucket[5m]))

# End-to-end request rate
rate(http_requests_total{job="frontend-stage3"}[1m])
```

### Logs (Loki)

Access Grafana Explore at http://localhost:3000/explore

**Key queries:**

```logql
# All die service logs
{container_name="die-service-stage3"} | json

# Die specification requests
{container_name="die-service-stage3"} | json | message =~ "specification requested"

# Dice roller querying die service
{container_name="dice-roller-stage3"} | json | message =~ "die service"

# Frontend logs
{container_name="frontend-stage3"} | json

# All error logs across all services
{container_name=~".*-stage3"} | json | level="ERROR"
```

### Traces (Tempo)

Access Grafana Explore → Tempo

**Search patterns:**
- Service name: `frontend`, `dice-roller`, `die-service`
- Filter by duration: `duration > 1s`
- Filter by span attributes: `die.type="risky"`

**Trace-to-Logs Correlation:**
1. Find a trace in Tempo
2. Click on any span
3. Click "Logs for this span" button
4. View correlated logs in Loki filtered by trace_id

## Grafana Dashboard

Import the Stage 3 dashboard:

1. Navigate to http://localhost:3000 → Dashboards → New → Import
2. Upload `grafana-dashboards/stage3-dashboard.json` (once created)
3. Or build manually using queries from `grafana-dashboards/README.md`

Dashboard includes:
- Die Service metrics and request rates
- Service-to-service communication metrics
- Frontend and Dice Roller metrics from previous stages
- Latency percentiles across all services
- Log panels for all services
- Instructions for viewing distributed traces

## Configuration Files

### Die Service - die_specifications.json

```json
{
  "fair": {
    "faces": [1, 2, 3, 4, 5, 6],
    "error_rate": 0
  },
  "risky": {
    "faces": [2, 3, 4, 5, 6, 7],
    "error_rate": 0.1
  }
}
```

**Adding new die types:**
1. Edit `die-service/die_specifications.json`
2. Add new entry with `faces` array and `error_rate` float
3. Restart die service: `docker compose restart die-service`
4. New die type automatically appears in frontend dropdown

### Docker Compose

Services use these port mappings:
- Frontend: `8105:8000`
- Dice Roller: `8104:8000`
- Die Service: `8103:8000`

All services:
- Connected to external `monitoring` network
- Export traces to OTel Collector
- Export metrics at `/metrics`
- Log JSON to stdout (collected by Alloy)

## Testing Scenarios

### 1. Happy Path Test

```bash
# Test die service directly
curl http://localhost:8103/dice
curl http://localhost:8103/dice?identifier=fair

# Test through dice roller
curl "http://localhost:8104/roll?die=fair"

# Test through frontend
curl "http://localhost:8105/roll?die=fair"
```

### 2. Error Handling - Unknown Die Type

```bash
# Should return 404
curl http://localhost:8103/dice?identifier=unknown

# Should return 503 (die service unavailable or not found)
curl "http://localhost:8104/roll?die=unknown"
```

### 3. Service Dependency Test

```bash
# Stop die service
docker compose stop die-service

# Try to roll - should fail gracefully
curl "http://localhost:8104/roll?die=fair"

# Check logs for error handling
docker compose logs dice-roller | grep -i "die service"

# Restart die service
docker compose start die-service

# Verify recovery
curl "http://localhost:8104/roll?die=fair"
```

### 4. Trace Verification

1. Generate some traffic: `cd traffic-gen && python generate_traffic.py`
2. Navigate to Grafana → Explore → Tempo
3. Search by `service.name="frontend"`
4. Select a trace
5. Verify trace includes spans from all 3 services:
   - frontend (HTTP request)
   - dice-roller (HTTP request + HTTP client to die-service)
   - die-service (HTTP request)
6. Click on dice-roller span → "Logs for this span"
7. Verify correlated logs appear

## Common Issues

### Services Can't Communicate

**Symptoms:** Connection errors, 503 responses

**Solutions:**
- Verify all services on `monitoring` network: `docker network inspect monitoring`
- Check DNS resolution: `docker exec dice-roller-stage3 ping die-service-stage3`
- Check service logs: `docker compose logs`

### No Traces in Tempo

**Symptoms:** Traces not appearing in Grafana

**Solutions:**
- Verify OTel Collector is running: `docker compose --project-directory stack ps otel-collector`
- Check collector logs: `docker compose --project-directory stack logs otel-collector`
- Verify OTEL environment variables in docker-compose.yml
- Test collector endpoint: `curl http://localhost:4318/v1/traces`

### No Logs in Loki

**Symptoms:** Logs not appearing in Grafana Explore

**Solutions:**
- Verify Alloy is running: `docker compose --project-directory stack ps alloy`
- Check Alloy UI: http://localhost:12345
- Verify container labels match Alloy filter regex
- Check Alloy logs: `docker compose --project-directory stack logs alloy`

### Metrics Not Scraped

**Symptoms:** Metrics not in Prometheus

**Solutions:**
- Check Prometheus targets: http://localhost:9090/targets
- Verify services are UP (green) in targets page
- Verify services expose `/metrics`: `curl http://localhost:8103/metrics`
- Check prometheus.yml includes stage3 scrape configs

## Cleanup

```bash
# Stop services
docker compose down

# Remove volumes (clears all data)
docker compose down -v
```

## Next Steps

After completing Stage 3:

1. **Stage 4**: Add async rolling endpoint with concurrent operations
2. **Experiment**: Add custom die types to die_specifications.json
3. **Performance**: Analyze service-to-service latency in traces
4. **Resilience**: Test behavior when services fail

## Key Learnings from Stage 3

- **Service Decomposition**: Breaking functionality into multiple services
- **Service Discovery**: Using Docker DNS for service communication
- **Trace Propagation**: How trace context flows through multiple services
- **Service Dependencies**: Managing startup order and failure handling
- **Configuration Management**: Centralizing configuration in a service
- **Observability Complexity**: More services = more spans, logs, and metrics to correlate

## Related Documentation

- [Stage 1 README](../stage1/README.md) - Single service basics
- [Stage 2 README](../stage2/README.md) - Frontend + Backend
- [Implementation Notes](../implementation-notes.md) - Code patterns
- [Overview](../overview.md) - All stages specification
