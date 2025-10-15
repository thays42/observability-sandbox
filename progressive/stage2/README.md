# Stage 2: Streamlit Frontend with Distributed Tracing

## Overview

Stage 2 adds a Streamlit frontend to demonstrate distributed tracing across two services. This stage shows:

- **Distributed Tracing**: W3C Trace Context propagation from frontend to backend
- **Two-Service Architecture**: Streamlit frontend → FastAPI backend
- **Frontend Instrumentation**: Metrics, logs, and traces from the UI layer
- **Trace Correlation**: Full request flow visibility across services

## Architecture

```
┌──────────────────┐      ┌─────────────────┐
│   Streamlit      │─────→│  Dice Roller    │
│   Frontend       │      │   (FastAPI)     │
│   Port 8102      │      │   Port 8101     │
└──────────────────┘      └─────────────────┘
        │                         │
        └─────────┬───────────────┘
                  ↓
         Prometheus (metrics)
         Loki via Alloy (logs)
         Tempo via OTel Collector (traces)
```

## Services

### Streamlit Frontend (Port 8102)

**Features**:
- Web UI with dropdown (fair/risky) and Roll button
- Makes HTTP requests to backend with trace context headers
- Displays roll results and trace IDs
- Embedded Flask server for Prometheus `/metrics` endpoint

**Instrumentation**:
- **Metrics**: `streamlit_button_clicks_total`, `streamlit_requests_total`, `streamlit_request_duration_seconds`
- **Logs**: JSON with trace_id, span_id, die_type, backend_status
- **Traces**: W3C Trace Context propagated via HTTP headers to backend

### Dice Roller Backend (Port 8101)

Same FastAPI service as Stage 1, configured for Stage 2.

## Prerequisites

1. Main observability stack running:
   ```bash
   cd /Users/thays/Projects/observability/sandbox
   make stack
   ```

2. Python 3.13+ with uv installed

## Quick Start

### 1. Start Services

```bash
cd specs/illustrative-python/stage2
docker compose up -d --build
```

### 2. Verify Services

```bash
# Check both services are running
docker compose ps

# Test backend
curl http://localhost:8101/

# Test frontend metrics endpoint
curl http://localhost:8102/metrics

# Access frontend UI
open http://localhost:8102
```

### 3. Restart Stack Services

```bash
cd /Users/thays/Projects/observability/sandbox
docker compose --project-directory stack restart prometheus
```

### 4. Use the Frontend

1. Open http://localhost:8102 in browser
2. Select die type (fair or risky)
3. Click "Roll" button
4. See result and trace ID
5. Copy trace ID and search in Tempo

### 5. Generate Traffic

```bash
cd specs/illustrative-python/stage2/traffic-gen

# Install dependencies
uv pip install -r pyproject.toml

# Run traffic generation (simulates frontend→backend with trace propagation)
python generate_traffic.py
```

### 6. View Distributed Traces

1. Navigate to Grafana → Explore → Tempo
2. Search by service name: `streamlit-frontend` or `dice-roller`
3. Click on a trace to see 2-service waterfall
4. Observe trace context propagation (same trace_id across services)

## Key Concepts Demonstrated

### W3C Trace Context Propagation

The frontend uses OpenTelemetry's `inject()` function to add trace context headers:

```python
from opentelemetry.propagate import inject

headers = {}
inject(headers)  # Adds traceparent and tracestate headers
response = requests.get(backend_url, headers=headers)
```

The backend automatically extracts these headers via FastAPI instrumentation, creating a parent-child span relationship.

### Distributed Trace Structure

```
Frontend Request (streamlit-frontend)
└─ HTTP GET /roll (dice-roller)
   └─ Roll operation
```

Both spans share the same `trace_id` but have different `span_id`s, allowing Tempo to reconstruct the full request flow.

### Trace-to-Logs Correlation

Both services log with `trace_id` and `span_id`, enabling:
1. Click on span in Tempo
2. Click "Logs for this span"
3. See logs from both frontend and backend for that request

## Instrumentation Details

### Frontend Metrics

**Prometheus Metrics** (exposed at http://localhost:8102/metrics):
- `streamlit_button_clicks_total{die_type}` - Counter of button clicks
- `streamlit_requests_total{die_type, status_code}` - Counter of backend requests
- `streamlit_request_duration_seconds{die_type}` - Histogram of request durations

**Implementation**: Embedded Flask server runs in background thread alongside Streamlit.

### Frontend Logs

**Format**: Structured JSON to stdout

**Fields**:
- `timestamp`, `level`, `message`, `logger`
- `trace_id`, `span_id` - For correlation
- `die_type` - Selected die type
- `backend_status` - HTTP status from backend
- `roll_value` - Result from backend (on success)

**Collection**: Grafana Alloy → Loki

### Frontend Traces

**Service Name**: `streamlit-frontend`

**Spans**:
- `roll_button_click` - Created on button press
- HTTP request span automatically created by `requests` instrumentation
- Trace context injected into request headers

**Attributes**:
- `die.type` - fair or risky
- `backend.status_code` - HTTP status
- `backend.url` - Backend endpoint called
- `roll.value` - Result (on success)

## Testing Checklist

### ✅ Service Health

- [ ] Both services start: `docker compose ps`
- [ ] Backend responds: `curl http://localhost:8101/`
- [ ] Frontend UI loads: Open http://localhost:8102
- [ ] Frontend metrics exposed: `curl http://localhost:8102/metrics`
- [ ] Backend metrics exposed: `curl http://localhost:8101/metrics`

### ✅ Metrics Collection

- [ ] Prometheus scraping both services: http://localhost:9090/targets
- [ ] Frontend metrics present: Query `streamlit_button_clicks_total` in Prometheus
- [ ] Backend metrics present: Query `dice_rolls_total` in Prometheus

### ✅ Log Collection

- [ ] Alloy discovering containers: http://localhost:12345
- [ ] Frontend logs in Loki: `{container_name="streamlit-frontend-stage2"}`
- [ ] Backend logs in Loki: `{container_name="dice-roller-stage2"}`
- [ ] Logs include trace context: Check for `trace_id` and `span_id` fields

### ✅ Distributed Tracing

- [ ] Frontend traces in Tempo: Search by `service.name="streamlit-frontend"`
- [ ] Backend traces in Tempo: Search by `service.name="dice-roller"`
- [ ] Traces show 2-service span: Frontend span contains backend child span
- [ ] Same trace_id across services: Verify in trace waterfall view
- [ ] Trace timing makes sense: Backend span is subset of frontend span duration

### ✅ Trace Context Propagation

- [ ] Make a roll via frontend UI
- [ ] Find the trace in Tempo (copy trace ID from UI or search)
- [ ] Verify trace has spans from BOTH services
- [ ] Check span parent-child relationship in waterfall
- [ ] Verify traceparent header was propagated (check span attributes)

### ✅ Trace-to-Logs Correlation

- [ ] Open a trace in Tempo
- [ ] Click on frontend span → "Logs for this span"
- [ ] Verify frontend logs appear with matching trace_id
- [ ] Click on backend span → "Logs for this span"
- [ ] Verify backend logs appear with matching trace_id
- [ ] Both sets of logs have the same trace_id

### ✅ Frontend UI

- [ ] Dropdown shows "fair" and "risky" options
- [ ] Roll button works and shows result
- [ ] Trace ID displayed in expandable section
- [ ] Error handling works: Backend errors displayed in UI
- [ ] Sidebar shows backend URL and info

### ✅ Traffic Generation

- [ ] Traffic script installs dependencies
- [ ] Script runs successfully: `python generate_traffic.py`
- [ ] Script simulates frontend with trace propagation
- [ ] Script logs show user activity and trace context
- [ ] Traces from script appear in Tempo with service name `traffic-generator`

### ✅ Dashboard

- [ ] Stage 2 Dashboard appears in Grafana
- [ ] All panels load without errors
- [ ] Backend metrics panels show data (inherited from Stage 1)
- [ ] Frontend metrics panels show data (Note: dashboard currently has Stage 1 panels only, needs manual addition of frontend panels)

## Troubleshooting

### Frontend can't connect to backend

```bash
# Check backend is accessible from frontend container
docker exec streamlit-frontend-stage2 curl http://dice-roller-stage2:8000/

# Check both services are on monitoring network
docker inspect dice-roller-stage2 | grep monitoring
docker inspect streamlit-frontend-stage2 | grep monitoring
```

### Trace context not propagating

```bash
# Check frontend logs for trace_id
docker logs streamlit-frontend-stage2 | grep trace_id

# Check backend logs for same trace_id
docker logs dice-roller-stage2 | grep trace_id

# Verify OpenTelemetry instrumentation
# Frontend should use opentelemetry-instrumentation-requests
# Backend should use opentelemetry-instrumentation-fastapi
```

### Metrics endpoint not working

```bash
# Frontend metrics (Flask on port 8501)
curl http://localhost:8102/metrics

# If not working, check Flask server started
docker logs streamlit-frontend-stage2 | grep "Running on"

# Backend metrics (prometheus-fastapi-instrumentator)
curl http://localhost:8101/metrics
```

### Frontend UI not loading

```bash
# Check Streamlit logs
docker logs streamlit-frontend-stage2

# Check if port 8102 is in use
lsof -i :8102

# Access Streamlit directly
# Default port is 8501 inside container, mapped to 8102 on host
```

## Ports

- **8101**: Dice roller backend HTTP API
- **8102**: Streamlit frontend UI (web browser)

## Configuration Files

- **Frontend**: `streamlit-frontend/app.py` - Streamlit app with embedded Flask metrics server
- **Frontend Dependencies**: `streamlit-frontend/pyproject.toml`
- **Frontend Container**: `streamlit-frontend/Dockerfile`
- **Backend**: `dice-roller/main.py` - Same as Stage 1
- **Compose**: `docker-compose.yml` - Both services with trace configuration
- **Traffic**: `traffic-gen/generate_traffic.py` - Simulates frontend requests with trace propagation
- **Dashboard**: `grafana-dashboards/stage2-dashboard.json` - Grafana dashboard (currently Stage 1 base, needs frontend panels)

## Key Learning Points

1. **W3C Trace Context** - Standard for trace propagation across services via HTTP headers
2. **Context Injection** - `inject(headers)` adds traceparent header to outgoing requests
3. **Context Extraction** - Backend automatically extracts context from headers
4. **Parent-Child Spans** - Frontend span is parent, backend span is child
5. **Shared Trace ID** - Both services use same trace_id, different span_ids
6. **Service Dependency** - Trace waterfall shows which service called which
7. **End-to-End Latency** - Total request time visible in frontend span
8. **Service-Level Latency** - Backend processing time visible in backend span
9. **Embedded Metrics Server** - Flask can run alongside Streamlit for Prometheus
10. **Distributed Logging** - Same trace_id in logs from multiple services

## Next Steps

Once Stage 2 is working:

1. Verify distributed tracing works (same trace_id across services)
2. Practice finding traces: Frontend → Tempo search → View 2-service waterfall
3. Test trace-to-logs: Span → Logs button → See correlated logs
4. Understand latency breakdown: Frontend span = backend span + network + overhead
5. Ready for **Stage 3**: Adding a third service (Die Service) for 3-hop distributed tracing

## Differences from Stage 1

- ✨ **New**: Streamlit frontend web UI
- ✨ **New**: Distributed tracing across 2 services
- ✨ **New**: W3C Trace Context propagation
- ✨ **New**: Frontend metrics (button clicks, request duration)
- ✨ **New**: Traffic generator simulates trace propagation
- 🔧 **Changed**: Backend on port 8101 (was 8100)
- 🔧 **Changed**: Frontend on port 8102 (new)
- 📊 **Same**: Backend implementation identical to Stage 1
- 📊 **Same**: All Stage 1 instrumentation still present
