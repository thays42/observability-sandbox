# OpenTelemetry Integration - Remaining Tasks

## Completed Work (Phases 1-2)

### Phase 1: Infrastructure ✅
- **Tempo**: Added to stack, running on port 3200, storing traces locally
  - Config: `stack/tempo/tempo-config.yml`
  - 48h trace retention
  - Receiving traces via OTLP from OTel Collector

- **OpenTelemetry Collector**: Gateway pattern deployment
  - Config: `stack/otel-collector/otel-collector-config.yml`
  - Receives OTLP on ports 4317 (gRPC) and 4318 (HTTP)
  - Forwards traces to Tempo
  - Note: Using `debug` exporter (not deprecated `logging` exporter)

- **Grafana Tempo Datasource**: Provisioned with trace-to-logs correlation
  - Config: `stack/grafana/provisioning/datasources/tempo.yml`
  - Custom query for trace-to-logs: `{job=~".+"} | json | trace_id=\`${__trace.traceId}\``
  - Works by parsing JSON logs and filtering by trace_id field

### Phase 2: Python App (dice-roller) ✅
- **Automatic Instrumentation**: Using `opentelemetry-instrument` wrapper
  - Dependencies added to `pyproject.toml`:
    - `opentelemetry-distro>=0.48b0`
    - `opentelemetry-exporter-otlp>=1.27.0`
    - `opentelemetry-instrumentation-fastapi>=0.48b0`
  - Dockerfile CMD: `uv run opentelemetry-instrument uvicorn main:app ...`

- **OTLP Export Configuration** (environment variables in docker-compose.yml):
  - `OTEL_SERVICE_NAME=dice-roller`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
  - `OTEL_TRACES_EXPORTER=otlp`
  - `OTEL_METRICS_EXPORTER=none` (keeping Prometheus scraping)
  - `OTEL_LOGS_EXPORTER=none` (using Loki via Docker driver)

- **Trace Context in Logs**: Custom JSONFormatter in `main.py`
  - Extracts trace_id, span_id, trace_flags from OpenTelemetry context
  - Logs include these fields in JSON format
  - Loki captures via Docker logging driver
  - **Trace-to-logs correlation verified working in Grafana**

### Key Learnings & Patterns

1. **Port Conflicts**: Tempo and OTel Collector both support OTLP - only expose OTel Collector ports (gateway pattern)

2. **Debug vs Logging Exporter**: OTel Collector 0.115.x deprecated `logging` exporter, use `debug` instead

3. **Trace-to-Logs Query**: Needs custom query because:
   - Service name in traces (`dice-roller`) ≠ container name in Loki (`demo-fastapi-rolldice`)
   - Solution: Query all logs, parse JSON, filter by trace_id field

4. **Docker Compose Build Context**: When using `--project-directory`, need to explicitly set `context: .` in build config

## Remaining Work

### Phase 3: R Shiny App (shiny-curl-gui)
**Status**: Not started
**Complexity**: HIGH (R's OTel support is nascent)

#### Tasks:
1. **Add otel and otelsdk R packages**
   - Update `shiny-curl-gui/renv.lock`
   - Package docs: https://otel.r-lib.org/
   - May need to install from GitHub if not on CRAN

2. **Manual instrumentation in app.R**
   - Create tracer provider
   - Configure OTLP HTTP exporter (port 4318)
   - Wrap request handlers with manual spans
   - Add span attributes: http.method, http.url, http.status_code

3. **Add trace context to logging**
   - Extract trace_id/span_id from active span
   - Add to logger metadata (currently using `logger` package)
   - Ensure JSON output includes trace fields

4. **Docker setup**
   - Add OTEL environment variables to docker-compose.yml
   - Service name: `shiny-curl-gui`
   - Endpoint: `http://otel-collector:4318/v1/traces`

5. **Validation**
   - Generate requests via Shiny GUI
   - Verify traces appear in Tempo
   - Verify logs contain trace_id
   - Test trace-to-logs correlation in Grafana

#### Expected Challenges:
- Limited R examples/documentation for OpenTelemetry
- May need significant manual span management
- R package stability (very new packages)

### Phase 4: Dashboards & Final Validation
**Status**: Not started

#### Tasks:
1. **Import/create Grafana dashboards**
   - Look for pre-built Tempo/tracing dashboards (Grafana.com)
   - Consider creating custom RED metrics dashboard
   - Create service graph visualization
   - Provision via `stack/grafana/provisioning/dashboards/`

2. **End-to-end testing**
   - Generate traffic through both apps
   - Verify all traces appear in Tempo
   - Test trace-to-logs navigation (both apps)
   - Test trace-to-metrics navigation (if configured)
   - Validate service graph shows both services

3. **Performance validation**
   - Check trace latency/overhead
   - Verify OTel Collector isn't bottleneck
   - Confirm Tempo storage is working

### Documentation Updates
**Status**: Not started

#### Tasks:
1. **Update CLAUDE.md** with:
   - OpenTelemetry architecture section
   - How to view traces in Grafana
   - How to use trace-to-logs correlation
   - How to add new services to tracing
   - Troubleshooting section

2. **Add OpenTelemetry to README** (if exists)

3. **Document configuration patterns**:
   - Environment variables for OTLP export
   - Trace context in logging pattern
   - Grafana datasource correlation setup

## Testing Procedures

### Verify Traces Flow
```bash
# Generate test traffic
curl http://localhost:8001/roll/3d6

# Check OTel Collector received traces
docker logs otel-collector --tail 50 | grep "Trace ID"

# Query Tempo for traces
curl -s "http://localhost:3200/api/search?tags=service.name%3Ddice-roller&limit=5" | jq '.traces'

# Get specific trace
curl -s "http://localhost:3200/api/traces/<TRACE_ID>" | jq '.'
```

### Verify Trace-to-Logs Correlation
```bash
# Get trace ID from recent request
TRACE_ID="<from logs or Tempo>"

# Query Loki for logs with that trace ID
curl -s 'http://localhost:3100/loki/api/v1/query_range' \
  --get \
  --data-urlencode 'query={job=~".+"} | json | trace_id=`'$TRACE_ID'`' \
  | jq '.data.result'
```

### Grafana UI Testing
1. Explore → Tempo → Search by Trace ID
2. Click trace → Expand span → "Logs for this span"
3. Should show correlated Loki logs

## Architecture Diagram

```
Applications (dice-roller, shiny-curl-gui)
    |
    | OTLP/HTTP (port 4318)
    v
OpenTelemetry Collector (Gateway)
    |
    | OTLP/gRPC (internal)
    v
Tempo (Trace Storage)
    ^
    | HTTP API (port 3200)
    |
Grafana
    |
    | Also queries Loki for trace-to-logs correlation
    v
Loki (contains JSON logs with trace_id fields)
```

## Next Steps

1. **Immediate**: Start Phase 3 - R Shiny app instrumentation
2. **After Phase 3**: Add dashboards and complete final validation
3. **Final**: Update all documentation

## Notes for Future Work

- Consider adding span metrics generation in Tempo
- May want to add trace sampling if volume increases
- Could explore Grafana Tempo's TraceQL for advanced queries
- Might want to add alerting based on trace error rates
