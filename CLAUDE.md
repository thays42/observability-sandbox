# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an observability stack built with Docker Compose, consisting of Prometheus for metrics collection, Loki for log aggregation, Tempo for distributed tracing, and Grafana for visualization. The stack is designed for monitoring applications and infrastructure with full observability (metrics, logs, and traces).

## Architecture

The project is organized into three separate docker-compose stacks:

### Stack (`stack/`)
The core observability infrastructure with its own [docker-compose.yml](stack/docker-compose.yml):

- **Prometheus**: Metrics collection and storage (port 9090)
  - Configuration: [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml)
  - Data persisted in `stack_prometheus-data` volume
  - Scrapes itself and demo-fastapi-rolldice every 15 seconds by default

- **Loki**: Log aggregation and storage (port 3100)
  - Configuration: [stack/loki/loki-config.yml](stack/loki/loki-config.yml)
  - Data persisted in `stack_loki-data` volume
  - Receives logs from demo apps via Grafana Alloy
  - Retention: 744 hours (31 days)

- **Tempo**: Distributed tracing storage (port 3200)
  - Configuration: [stack/tempo/tempo-config.yml](stack/tempo/tempo-config.yml)
  - Data persisted in `stack_tempo-data` volume
  - Receives traces via OTLP from OpenTelemetry Collector
  - Retention: 48 hours

- **OpenTelemetry Collector**: Trace collection gateway (ports 4317/4318)
  - Configuration: [stack/otel-collector/otel-collector-config.yml](stack/otel-collector/otel-collector-config.yml)
  - Receives OTLP traces via gRPC (4317) and HTTP (4318)
  - Forwards traces to Tempo
  - Batch processing with memory limits

- **Grafana Alloy**: Log collection agent (port 12345 for UI)
  - Configuration: [stack/alloy/config.alloy](stack/alloy/config.alloy)
  - Collects logs from dice-roller and shiny-curl-gui containers only
  - Forwards logs to Loki with labels: container_name, compose_project, compose_service, job
  - Parses JSON logs and extracts trace_id, span_id for correlation
  - Uses discovery.docker for automatic container discovery with relabeling filters

- **Grafana**: Metrics, logs, and traces visualization (port 3000)
  - Configuration: [stack/grafana/grafana.ini](stack/grafana/grafana.ini)
  - Datasource provisioning: [stack/grafana/provisioning/datasources/](stack/grafana/provisioning/datasources/)
  - Data persisted in `stack_grafana-data` volume
  - Pre-configured with Prometheus (default), Loki, and Tempo datasources
  - Trace-to-logs correlation enabled via custom query
  - Anonymous viewing enabled, admin credentials: admin/admin

### Demo Applications

- **dice-roller**: Demo FastAPI application (port 8001)
  - Source: [dice-roller/](dice-roller/)
  - Compose file: [dice-roller/docker-compose.yml](dice-roller/docker-compose.yml)
  - Python 3.13 managed with uv
  - Provides `/roll/{dice}` endpoint (e.g., `/roll/3d6`)
  - Exposes Prometheus metrics at `/metrics` using prometheus-fastapi-instrumentator
  - **OpenTelemetry**: Automatic instrumentation with trace context in JSON logs
    - Traces exported via OTLP HTTP to OTel Collector
    - Logs include `trace_id` and `span_id` for correlation

- **shiny-curl-gui**: Demo R Shiny application (port 8002)
  - Source: [shiny-curl-gui/](shiny-curl-gui/)
  - Compose file: [shiny-curl-gui/docker-compose.yml](shiny-curl-gui/docker-compose.yml)
  - R 4.5.1 (rocker/r-ver base image) with httr2 for HTTP requests, logger for JSON logging
  - GUI for making HTTP requests (GET, POST, PUT, DELETE)
  - Displays formatted response with status code, headers, and body
  - Uses binary packages from Posit Package Manager for faster builds on ARM
  - Structured JSON logging with session tracking (UUID-based)
  - Logs: INFO (app start, sessions), DEBUG (requests), INFO/WARN/ERROR (responses by status code)
  - **OpenTelemetry**: Manual instrumentation using `otel` and `otelsdk` R packages
    - Traces exported via OTLP HTTP to OTel Collector
    - Environment variable: `OTEL_R_TRACES_EXPORTER=http` required to enable tracing
    - Logs include `trace_id` and `span_id` via `span$get_context()$get_trace_id()` methods
  - TODO: Add request body and custom headers support

All services communicate via the `monitoring` Docker network (must be created before starting services).

## Common Commands

A [Makefile](Makefile) is provided for convenience:

### Starting Services
```bash
# Start everything (requires monitoring network to exist)
make all

# Start individual stacks
make stack          # Prometheus, Loki, Grafana
make dice-roller    # FastAPI demo app
make shiny-curl-gui # R Shiny demo app
```

### Stopping Services
```bash
# Stop all services
make down

# Clean up (stop + remove volumes)
make clean
```

### Manual Docker Compose Commands
```bash
# Start a specific stack
docker compose --project-directory stack up -d
docker compose --project-directory dice-roller up -d
docker compose --project-directory shiny-curl-gui up -d

# Stop a specific stack
docker compose --project-directory stack down
docker compose --project-directory dice-roller down
docker compose --project-directory shiny-curl-gui down
```

### Viewing Logs
```bash
# Via Docker (specific stack)
docker compose --project-directory stack logs -f
docker compose --project-directory dice-roller logs -f
docker compose --project-directory shiny-curl-gui logs -f

# Specific service
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f loki

# Query logs via Loki (all containers send logs to Loki)
# Use Grafana Explore with Loki datasource or query directly:
curl 'http://localhost:3100/loki/api/v1/query_range' \
  --get --data-urlencode 'query={container_name="shiny-curl-gui"}'
```

### Restarting After Configuration Changes
```bash
# Restart services in the stack
docker compose --project-directory stack restart prometheus
docker compose --project-directory stack restart loki
docker compose --project-directory stack restart grafana
```

### Accessing Services
- Prometheus UI: http://localhost:9090
- Loki API: http://localhost:3100 (ready check at http://localhost:3100/ready)
- Tempo API: http://localhost:3200 (ready check at http://localhost:3200/ready)
- Alloy UI: http://localhost:12345 (view discovered targets and config)
- Grafana UI: http://localhost:3000 (Explore view for logs and traces)
- Demo Dice Roller API: http://localhost:8001 (metrics at http://localhost:8001/metrics)
- Shiny cURL GUI: http://localhost:8002

## Configuration Structure

### Prometheus
- Global scrape and evaluation interval: 15s
- Add new scrape targets in [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml) under `scrape_configs`
- Configuration is mounted read-only from host

### Loki
- Demo apps send logs to Loki via Grafana Alloy
- Logs queryable by labels: `container_name`, `job`, `compose_project`, `compose_service`
- Configuration in [stack/loki/loki-config.yml](stack/loki/loki-config.yml)
- 31-day retention period

### Grafana Alloy
- Discovers Docker containers via Docker socket
- Filters to collect logs only from dice-roller and shiny-curl-gui
- Configuration in [stack/alloy/config.alloy](stack/alloy/config.alloy) using Alloy's River syntax
- Automatic relabeling to add container_name, compose_project, compose_service, job labels
- JSON log parsing to extract trace_id, span_id, level for trace-to-logs correlation

### Grafana
- Datasources are provisioned automatically from [stack/grafana/provisioning/datasources/](stack/grafana/provisioning/datasources/)
- To add dashboards, create a dashboard provisioning file in `stack/grafana/provisioning/dashboards/`
- Custom Grafana settings in [stack/grafana/grafana.ini](stack/grafana/grafana.ini)
- Query logs in Explore → Loki datasource → `{container_name="shiny-curl-gui"}`

### Tempo & OpenTelemetry
- Tempo stores traces received from the OpenTelemetry Collector
- Configuration in [stack/tempo/tempo-config.yml](stack/tempo/tempo-config.yml)
- Local storage backend with 48-hour retention
- OTel Collector acts as a gateway: apps → collector → Tempo
- Collector configuration in [stack/otel-collector/otel-collector-config.yml](stack/otel-collector/otel-collector-config.yml)

## Adding New Monitoring Targets

To monitor a new application or service:

1. **For metrics**: Add the target to [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml) under `scrape_configs`:
```yaml
- job_name: 'my-app'
  static_configs:
    - targets: ['my-app:8080']
```

2. **For logs**: Update Alloy configuration to include your app's compose project:
   - Edit [stack/alloy/config.alloy](stack/alloy/config.alloy)
   - In the `discovery.relabel` block, update the regex to include your project:
   ```alloy
   rule {
     source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
     regex         = "(dice-roller|shiny-curl-gui|my-app)"  # Add your project
     action        = "keep"
   }
   ```
   - Restart Alloy: `docker compose --project-directory stack restart alloy`

3. Add the service to the `monitoring` network:
```yaml
networks:
  monitoring:
    external: true
```

4. **For traces**: Configure OpenTelemetry in your application:
```yaml
my-app:
  environment:
    - OTEL_SERVICE_NAME=my-app
    - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
    - OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces
    # For Python apps with automatic instrumentation:
    - OTEL_TRACES_EXPORTER=otlp
    - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
    # For R apps using otelsdk:
    - OTEL_R_TRACES_EXPORTER=http
```

5. **For trace-to-logs correlation**: Add `trace_id` and `span_id` to your JSON logs:
   - **Python**: Use OpenTelemetry's trace context injection (see [dice-roller/main.py](dice-roller/main.py))
   - **R**: Use `span$get_context()$get_trace_id()` and `get_span_id()` (see [shiny-curl-gui/app.R](shiny-curl-gui/app.R))
   - Alloy will automatically extract these fields if your logs are in JSON format

6. Restart services: `docker compose --project-directory <your-app> up -d` and `docker compose --project-directory stack restart alloy`

## Viewing Traces

### Using Grafana Explore (Recommended)
1. Navigate to http://localhost:3000 → **Explore** (compass icon in sidebar)
2. Select **Tempo** datasource from dropdown
3. **Search** tab:
   - Search by service name (e.g., `dice-roller`, `shiny-curl-gui`)
   - Search by trace ID
   - Filter by time range
4. Click on a trace to view:
   - Span waterfall visualization
   - Span attributes (http.method, http.url, etc.)
   - Duration and timing information
5. **Trace-to-Logs Correlation**:
   - Click on any span
   - Click "Logs for this span" button
   - Automatically jumps to Loki with filtered logs by `trace_id`

### Using Tempo API
```bash
# Search for traces by service
curl "http://localhost:3200/api/search?tags=service.name%3Ddice-roller&limit=10"

# Get a specific trace
curl "http://localhost:3200/api/traces/<TRACE_ID>"

# Query logs with trace_id in Loki
curl 'http://localhost:3100/loki/api/v1/query_range' \
  --get --data-urlencode 'query={job=~".+"} | json | trace_id=`<TRACE_ID>`'
```

## User Preferences

### Communication Style
- Be very concise when summarizing what you will do or have done. I will ask you to provide more detail if I want it.
