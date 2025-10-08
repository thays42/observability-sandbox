# Observability Stack

A complete observability solution built with Docker Compose, providing metrics, logs, and distributed tracing for monitoring applications and infrastructure.

## 📋 Table of Contents

- [Components](#components)
- [Demo Applications](#demo-applications)
- [Data Flow Architecture](#data-flow-architecture)
- [Getting Started](#getting-started)
- [Using Grafana](#using-grafana)

## Components

### Core Observability Stack

#### Prometheus (Metrics)

Prometheus scrapes metrics from instrumented applications at regular intervals (default: 15s). It stores these metrics in a local time-series database and provides a powerful query language (PromQL) for analysis.

- **Purpose:** Time-series metrics collection and storage
- **Port:** 9090
- **Configuration:** [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml)
- **Storage:** Persistent volume `stack_prometheus-data`
- **Targets:** Self-monitoring + demo apps with `/metrics` endpoints

#### Loki (Logs)


Loki is a horizontally-scalable, highly-available log aggregation system inspired by Prometheus. Unlike traditional log systems, it indexes only metadata (labels) rather than full-text, making it cost-effective.

- **Purpose:** Log aggregation and storage
- **Port:** 3100
- **Configuration:** [stack/loki/loki-config.yml](stack/loki/loki-config.yml)
- **Storage:** Persistent volume `stack_loki-data`
- **Retention:** 31 days (744 hours)
- **Log Sources:** Receives logs from Grafana Alloy

#### Tempo (Traces)

Tempo stores distributed traces, allowing you to track requests as they flow through your system. It integrates with Loki and Prometheus for correlated observability.

- **Purpose:** Distributed tracing storage
- **Port:** 3200
- **Configuration:** [stack/tempo/tempo-config.yml](stack/tempo/tempo-config.yml)
- **Storage:** Persistent volume `stack_tempo-data`
- **Retention:** 48 hours
- **Protocol:** Receives traces via OpenTelemetry Protocol (OTLP)

#### OpenTelemetry Collector (Trace Gateway)

Acts as a centralized gateway for trace data. Applications send traces to the collector, which processes and forwards them to Tempo.

- **Purpose:** Trace collection and forwarding
- **Ports:** 4317 (gRPC), 4318 (HTTP)
- **Configuration:** [stack/otel-collector/otel-collector-config.yml](stack/otel-collector/otel-collector-config.yml)
- **Features:** Batch processing, memory limiting, protocol translation

#### Grafana Alloy (Log Collection)

Modern replacement for Promtail, Alloy discovers Docker containers automatically and streams their logs to Loki. It parses JSON logs and extracts trace correlation fields.

- **Purpose:** Log collection agent
- **Port:** 12345 (UI)
- **Configuration:** [stack/alloy/config.alloy](stack/alloy/config.alloy)
- **Discovery:** Automatic Docker container detection
- **Filtering:** Collects logs only from specified demo apps
- **Labels Added:** `container_name`, `compose_project`, `compose_service`, `job`
- **Parsing:** Extracts `trace_id`, `span_id`, `level` from JSON logs

#### Grafana (Visualization)

Grafana provides visualization for metrics, logs, and traces. Pre-configured datasources enable seamless correlation between all three pillars of observability.

- **Purpose:** Unified observability dashboard
- **Port:** 3000
- **Configuration:** [stack/grafana/grafana.ini](stack/grafana/grafana.ini)
- **Datasources:** Prometheus (default), Loki, Tempo
- **Credentials:** admin/admin
- **Features:** Trace-to-logs correlation, anonymous viewing enabled

## Demo Applications

### dice-roller (FastAPI + Python)

A simple REST API that simulates dice rolls, demonstrating the three pillars of observability.

- **Port:** 8001
- **Language:** Python 3.13 (managed with uv)
- **Framework:** FastAPI

**Endpoints:**
- `GET /roll/{dice}` - Roll dice (e.g., `/roll/3d6` rolls three 6-sided dice)
- `GET /metrics` - Prometheus metrics endpoint

**Observability Features:**
- **Metrics:** Exposed via `prometheus-fastapi-instrumentator` (request count, duration, etc.)
- **Logs:** Structured JSON logging with trace context
- **Traces:** Automatic OpenTelemetry instrumentation, exported via OTLP HTTP

**Generating Traffic:**
```bash
# Roll some dice
curl http://localhost:8001/roll/2d20
curl http://localhost:8001/roll/1d6
curl http://localhost:8001/roll/4d12

# View metrics
curl http://localhost:8001/metrics
```

### shiny-curl-gui (R Shiny)

An interactive web GUI for making HTTP requests, showcasing manual OpenTelemetry instrumentation in R.

- **Port:** 8002
- **Language:** R 4.5.1
- **Framework:** Shiny

**Features:**
- HTTP methods: GET, POST, PUT, DELETE
- Response display: status code, headers, formatted body
- Session tracking with UUID-based identifiers

**Observability Features:**
- **Logs:** Structured JSON logging with `logger` package
  - INFO: App start, session creation
  - DEBUG: Request details
  - INFO/WARN/ERROR: Responses (status code-based)
- **Traces:** Manual instrumentation using `otel` and `otelsdk` R packages
  - Trace/span context manually propagated to logs
  - Exported via OTLP HTTP (requires `OTEL_R_TRACES_EXPORTER=http`)

**Generating Traffic:**
```bash
# Open the GUI in your browser
open http://localhost:8002

# Use the GUI to make requests to:
# - http://localhost:8001/roll/2d6 (GET)
```

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEMO APPLICATIONS                            │
├─────────────────────────────────┬───────────────────────────────────┤
│   dice-roller (FastAPI/Python)  │  shiny-curl-gui (R Shiny)         │
│                                 │                                   │
│   • /roll/{dice} endpoint       │  • HTTP request GUI               │
│   • /metrics endpoint           │  • Session tracking               │
│   • Auto instrumentation        │  • Manual instrumentation         │
└─────────────────────────────────┴───────────────────────────────────┘
         │                │                      │              │
         │ Metrics        │ Logs                 │ Logs         │ Traces
         │ (Prometheus)   │ (JSON)               │ (JSON)       │ (OTLP)
         ▼                ▼                      ▼              ▼
┌──────────────────┐  ┌────────────────────────────────┐  ┌─────────────┐
│   PROMETHEUS     │  │       GRAFANA ALLOY            │  │ OTEL        │
│                  │  │                                │  │ COLLECTOR   │
│  • Scrapes /     │  │  • Docker discovery            │  │             │
│    metrics every │  │  • Container filtering         │  │ • Receives  │
│    15s           │  │  • JSON log parsing            │  │   OTLP      │
│  • Stores time-  │  │  • Extract trace_id/span_id    │  │ • Batching  │
│    series data   │  │  • Add labels                  │  │ • Forwards  │
└──────────────────┘  └────────────────────────────────┘  └─────────────┘
         │                             │                          │
         │                             ▼                          ▼
         │                    ┌─────────────────┐        ┌──────────────┐
         │                    │     LOKI        │        │    TEMPO     │
         │                    │                 │        │              │
         │                    │ • Stores logs   │        │ • Stores     │
         │                    │ • Label indexing│        │   traces     │
         │                    │ • 31-day retain │        │ • 48h retain │
         │                    └─────────────────┘        └──────────────┘
         │                             │                          │
         └─────────────────────────────┴──────────────────────────┘
                                       │
                                       ▼
                            ┌────────────────────┐
                            │     GRAFANA        │
                            │                    │
                            │ • Explore view     │
                            │ • Dashboards       │
                            │ • Correlation      │
                            │ • Visualization    │
                            └────────────────────┘
                                       │
                                       ▼
                                    👤 USER
```

### Data Flow Explanation

1. **Metrics Flow:**
   - Demo apps expose `/metrics` endpoints
   - Prometheus scrapes metrics every 15 seconds
   - Metrics stored in time-series database
   - Queryable via PromQL in Grafana

2. **Logs Flow:**
   - Apps write structured JSON logs to stdout/stderr
   - Alloy discovers containers via Docker API
   - Alloy filters for demo app containers only
   - JSON logs parsed to extract trace context (`trace_id`, `span_id`)
   - Logs forwarded to Loki with enriched labels
   - Queryable via LogQL in Grafana

3. **Traces Flow:**
   - Apps instrument code with OpenTelemetry SDKs
   - Traces sent to OTel Collector via OTLP (HTTP/gRPC)
   - Collector processes and forwards to Tempo
   - Traces stored with span relationships intact
   - Queryable via TraceQL in Grafana

4. **Correlation:**
   - Apps inject `trace_id` and `span_id` into logs
   - Alloy extracts these fields during ingestion
   - Grafana links traces to logs automatically
   - Click "Logs for this span" in trace view → filtered logs

## Getting Started

### Prerequisites
- Docker and Docker Compose
- The `monitoring` network must exist: `docker network create monitoring`

### Quick Start

```bash
# Start everything
make all

# Or start individually
make stack          # Core observability stack
make dice-roller    # FastAPI demo
make shiny-curl-gui # Shiny demo
```

### Generate Sample Traffic

```bash
# Generate dice roll requests (creates metrics, logs, traces)
for i in {1..10}; do curl http://localhost:8001/roll/2d6; done

# Use Shiny GUI (creates logs and traces)
# 1. Open http://localhost:8002
# 2. Enter URL: http://localhost:8001/roll/3d20
# 3. Click "Send Request"
```

### Access Services

- **Grafana:** http://localhost:3000 (admin/admin)
- **Prometheus:** http://localhost:9090
- **Alloy UI:** http://localhost:12345
- **dice-roller API:** http://localhost:8001
- **shiny-curl-gui:** http://localhost:8002

## Using Grafana

Access Grafana at http://localhost:3000 (credentials: admin/admin)

### Viewing Metrics

1. **Navigate to Explore:**
   - Click the compass icon (🧭) in the left sidebar
   - Select **Prometheus** from the datasource dropdown (top)

2. **Query Metrics:**
   - **Metric browser:** Click "Metrics browser" to see all available metrics
   - **PromQL examples:**
     ```promql
     # Request rate for dice-roller
     rate(http_requests_total{job="demo-fastapi-rolldice"}[5m])

     # Request duration by endpoint
     http_request_duration_seconds_bucket{job="demo-fastapi-rolldice"}

     # HTTP status codes
     http_requests_total{status=~"2.."}
     ```

3. **Visualization:**
   - **Time series:** Line graphs showing metrics over time
   - **Stats:** Current/min/max/avg values
   - **Table:** Raw metric data with labels

### Viewing Logs

1. **Navigate to Explore:**
   - Click the compass icon (🧭) in the left sidebar
   - Select **Loki** from the datasource dropdown

2. **Query Logs:**
   - **Label browser:** Click "Label browser" to filter by labels
   - **LogQL examples:**
     ```logql
     # All logs from dice-roller
     {container_name="dice-roller"}

     # All logs from shiny-curl-gui
     {container_name="shiny-curl-gui"}

     # Filter by log level (if extracted)
     {container_name="dice-roller"} | json | level="ERROR"

     # Search for specific text
     {container_name=~".+"} |= "roll"

     # Logs with trace context
     {job=~".+"} | json | trace_id!=""
     ```

3. **Log Details:**
   - Click on any log line to expand full details
   - JSON fields automatically parsed and displayed
   - `trace_id` and `span_id` shown when available

### Viewing Traces

1. **Navigate to Explore:**
   - Click the compass icon (🧭) in the left sidebar
   - Select **Tempo** from the datasource dropdown

2. **Search for Traces:**
   - **Search tab** (default):
     - **Service Name:** Select from dropdown (e.g., `dice-roller`, `shiny-curl-gui`)
     - **Time Range:** Adjust as needed (last 1 hour, 6 hours, etc.)
     - **Tags:** Optional filtering by span attributes
   - **TraceQL tab** (advanced):
     ```traceql
     # Find slow requests
     { duration > 100ms }

     # Filter by service
     { service.name = "dice-roller" }

     # HTTP errors
     { span.http.status_code >= 400 }
     ```

3. **Trace Visualization:**
   - **Waterfall view:** Shows span hierarchy and timing
   - **Span details:** Click any span to see:
     - Attributes (http.method, http.url, etc.)
     - Duration and timing
     - Service name and operation
   - **Minimap:** Navigate large traces easily

### Trace-to-Logs Correlation

1. **From a trace in Explore (Tempo):**
   - Click on any span in the trace waterfall
   - Look for **"Logs for this span"** button in the span details panel
   - Click the button

2. **Automatic navigation:**
   - Grafana switches to Loki datasource
   - Filters logs by `trace_id` automatically
   - Shows only logs from that specific trace
   - Time range adjusted to span duration

3. **Manual correlation:**
   - Copy `trace_id` from trace view
   - Switch to Loki datasource
   - Query: `{job=~".+"} | json | trace_id="<PASTE_TRACE_ID>"`

### Creating Dashboards

1. **From Explore:**
   - Build your query (metrics, logs, or traces)
   - Click **"Add to dashboard"** button (top right)
   - Choose existing dashboard or create new

2. **Dashboard features:**
   - **Panels:** Combine multiple visualizations
   - **Variables:** Dynamic filtering (e.g., by service name)
   - **Time controls:** Consistent time ranges across panels
   - **Refresh:** Auto-refresh for live monitoring

3. **Example dashboard panels:**
   - Request rate graph (Prometheus)
   - Error log stream (Loki)
   - P95 latency (Prometheus)
   - Recent traces table (Tempo)

### Pro Tips

- **Linked queries:** Shift+click on a metric label to filter by that label
- **Time sync:** All Explore queries share the same time range
- **Split view:** Click the split button to compare datasources side-by-side
- **Query history:** Access previous queries from the history tab
- **Shortcuts:** `Ctrl+K` for command palette, `Ctrl+Enter` to run query

## Cleanup

```bash
# Stop all services
make down

# Stop and remove volumes (deletes all data)
make clean
```

## Next Steps

- Review [CLAUDE.md](CLAUDE.md) for detailed configuration and development notes
- Explore the service configurations in the `stack/` directory
- Add your own applications to the observability stack
- Create custom Grafana dashboards for your use cases
