# Progressive Python Observability Demo

A six-stage progressive demonstration of instrumenting Python applications with OpenTelemetry for comprehensive observability (metrics, logs, and traces).

## Quick Links

- **[overview.md](overview.md)**: Complete specification for all 6 stages
- **[implementation-notes.md](implementation-notes.md)**: Practical implementation patterns and code examples

## Stage Summary

### Stage 1: Single FastAPI Service
**Goal:** Establish observability foundation

- **Service:** Dice rolling API (`/roll?die=fair|risky`)
- **New concepts:** 
  - Prometheus metrics (built-in + custom)
  - JSON structured logging with trace context
  - OpenTelemetry automatic instrumentation
  - Basic Grafana dashboard
- **Traffic generation:** Async Python script simulating multiple users

### Stage 2: Streamlit Frontend
**Goal:** Demonstrate distributed tracing across services

- **Service:** Streamlit web UI for dice rolling
- **New concepts:**
  - Frontend instrumentation
  - Trace context propagation (W3C Trace Context)
  - Distributed traces (frontend → backend)
  - Service dependency visualization
- **Traffic generation:** Simulate frontend-initiated requests with trace context

### Stage 3: Die Service
**Goal:** Three-service architecture with service-to-service communication

- **Service:** FastAPI service providing die specifications
- **New concepts:**
  - Three-service distributed traces (frontend → dice-roller → die-service)
  - Service-to-service metrics
  - Dynamic configuration loading
  - Service map visualization in Tempo
- **Traffic generation:** Test full request chain through all services

### Stage 4: Async Rolling
**Goal:** Demonstrate concurrent operations in traces

- **Endpoint:** `/roll-async?die=X&times=N` - roll N dice concurrently
- **New concepts:**
  - Parent/child span relationships
  - Concurrent span visualization (overlapping in trace waterfall)
  - Performance comparison metrics (sync vs async)
  - Async operation tracking
- **Traffic generation:** Performance comparison scripts

### Stage 5: Database Backend
**Goal:** Show database observability integration

- **Infrastructure:** PostgreSQL for die specifications
- **New concepts:**
  - Database instrumentation (automatic query spans)
  - Database metrics (postgres_exporter)
  - Database query visualization in traces
  - Connection pool monitoring
  - Resilience testing (database failures)
- **Traffic generation:** Database load testing, failure simulation

### Stage 6: Usage Tracking
**Goal:** Demonstrate selective log routing

- **Feature:** Simple sign-in flow, usage event tracking
- **New concepts:**
  - Log routing based on content (Alloy filtering)
  - Usage analytics separate from operational logs
  - Custom log fields for business metrics
- **Implementation:** Alloy routes logs with `"usage": true` to separate destination

## Technology Stack

**Application Layer:**
- FastAPI (backend services)
- Streamlit (frontend UI)
- Python 3.13 with uv package manager
- PostgreSQL (Stage 5+)

**Observability Stack:**
- **Metrics:** Prometheus, prometheus-fastapi-instrumentator, prometheus-client
- **Logs:** Loki, Grafana Alloy (collection agent)
- **Traces:** Tempo, OpenTelemetry Collector
- **Visualization:** Grafana

**OpenTelemetry Instrumentation:**
- `opentelemetry-instrumentation-fastapi` (automatic)
- `opentelemetry-instrumentation-requests` (automatic)
- `opentelemetry-instrumentation-psycopg2` (automatic, Stage 5)
- `opentelemetry-exporter-otlp` (OTLP HTTP exporter)

## Progressive Complexity

| Stage | Services | Observability Features | Infrastructure |
|-------|----------|----------------------|----------------|
| 1 | 1 | Metrics, Logs, Traces (single service) | FastAPI |
| 2 | 2 | Distributed traces, trace propagation | + Streamlit |
| 3 | 3 | Multi-hop traces, service maps | + Die Service |
| 4 | 3 | Concurrent operations, parent/child spans | + Async endpoint |
| 5 | 3 | Database traces, DB metrics | + PostgreSQL |
| 6 | 3 | Log routing, usage analytics | + Advanced Alloy config |

## Key Learning Outcomes

By the end of Stage 6, you will understand:

1. **Metrics:**
   - Automatic HTTP metrics (RED: Rate, Errors, Duration)
   - Custom business metrics (roll distributions, die types)
   - Service-to-service metrics
   - Database metrics

2. **Logs:**
   - Structured JSON logging
   - Trace context in logs (trace_id, span_id)
   - Log correlation with traces
   - Selective log routing

3. **Traces:**
   - Automatic instrumentation for FastAPI, requests, database
   - Trace context propagation (W3C standard)
   - Distributed tracing across multiple services
   - Parent/child span relationships
   - Database query spans

4. **Grafana:**
   - Building dashboards for each service
   - Querying metrics (PromQL)
   - Querying logs (LogQL)
   - Trace-to-logs correlation
   - Service dependency graphs

5. **Architecture:**
   - Microservices observability
   - Service-to-service communication patterns
   - Database integration observability
   - Async operation tracing

## Getting Started

### Prerequisites

1. Running observability stack (from main repo):
   ```bash
   cd /path/to/sandbox
   make stack  # Start Prometheus, Loki, Tempo, Grafana, OTel Collector
   ```

2. Docker and Docker Compose
3. Python 3.13+ with uv

### Implementation Order

Follow stages sequentially:

1. **Read** `overview.md` for the stage
2. **Implement** the application code
3. **Configure** instrumentation (metrics, logs, traces)
4. **Update** Alloy/Prometheus configs to collect data
5. **Create** Grafana dashboard
6. **Build** traffic generation script
7. **Test** and verify all three signals (metrics, logs, traces)
8. **Document** learnings before moving to next stage

### Verification Checklist (per stage)

- [ ] Service(s) start successfully
- [ ] `/metrics` endpoint exposes Prometheus metrics
- [ ] Logs appear in Loki with trace_id and span_id
- [ ] Traces appear in Tempo
- [ ] Grafana dashboard shows data in all panels
- [ ] Traffic generation script runs successfully
- [ ] Trace-to-logs correlation works (click "Logs for this span" in Tempo)
- [ ] Service graph/map shows all services

## Project Structure

```
specs/illustrative-python/
├── README.md                    # This file
├── overview.md                  # Complete specification
├── implementation-notes.md      # Code patterns and examples
├── stage1/
│   ├── docker-compose.yml
│   ├── dice-roller/            # FastAPI service
│   ├── traffic-gen/            # Traffic generation scripts
│   └── grafana-dashboards/     # Dashboard JSON
├── stage2/
│   ├── docker-compose.yml
│   ├── streamlit-frontend/     # Streamlit UI
│   └── ...
├── stage3/
│   ├── docker-compose.yml
│   ├── die-service/            # Die specification service
│   └── ...
├── stage4/
│   └── ...                     # Extends stage3 with async endpoint
├── stage5/
│   ├── docker-compose.yml      # + PostgreSQL
│   └── ...
└── stage6/
    └── ...                     # Usage tracking additions
```

## Common Commands

```bash
# Start a stage
cd stageN
docker compose up -d

# View logs
docker compose logs -f service-name

# Stop a stage
docker compose down

# Clean up (including volumes)
docker compose down -v

# Run traffic generation
cd stageN/traffic-gen
python generate_traffic.py

# Check service health
curl http://localhost:PORT/
curl http://localhost:PORT/metrics

# Query Loki for logs
curl 'http://localhost:3100/loki/api/v1/query_range' \
  --get --data-urlencode 'query={container_name="service-name"}'

# Query Prometheus for metrics
curl 'http://localhost:9090/api/v1/query?query=dice_rolls_total'
```

## Useful Grafana Queries

### Loki (Logs)

```logql
# All logs for a service
{container_name="dice-roller"} | json

# Error logs only
{container_name="dice-roller"} | json | level="ERROR"

# Logs for specific trace
{container_name="dice-roller"} | json | trace_id="abc123..."

# Usage logs
{container_name="streamlit-frontend"} | json | usage="true"
```

### Prometheus (Metrics)

```promql
# Request rate
rate(http_requests_total[1m])

# Error rate
rate(http_requests_total{status=~"5.."}[1m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Success rate percentage
sum(rate(http_requests_total{status!~"5.."}[5m])) 
  / sum(rate(http_requests_total[5m])) * 100
```

### Tempo (Traces)

- Search by service name: `service.name="dice-roller"`
- Search by span attribute: `die.type="risky"`
- Search by duration: `duration > 1s`

## Troubleshooting

See **Common Pitfalls and Solutions** section in `implementation-notes.md` for detailed troubleshooting guidance.

Quick checks:
1. Verify observability stack is running: `docker compose --project-directory stack ps`
2. Check service logs: `docker compose logs service-name`
3. Verify network connectivity: Services must be on `monitoring` network
4. Check Alloy UI: http://localhost:12345 - verify containers are discovered
5. Check Prometheus targets: http://localhost:9090/targets - verify scrape targets are up
6. Check OTel Collector: `docker compose --project-directory stack logs otel-collector`

## Resources

- [OpenTelemetry Python Documentation](https://opentelemetry.io/docs/instrumentation/python/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Query Examples](https://prometheus.io/docs/prometheus/latest/querying/examples/)
- [LogQL Documentation](https://grafana.com/docs/loki/latest/logql/)

## Contributing

When implementing stages, please:
1. Follow the patterns in `implementation-notes.md`
2. Document any deviations from the spec in `overview.md`
3. Include example traffic generation output
4. Export and commit Grafana dashboards as JSON
5. Test trace-to-logs correlation before moving to next stage

## License

This demo is part of the observability sandbox project.
