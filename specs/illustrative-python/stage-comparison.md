# Stage-by-Stage Comparison

This document provides a visual comparison of what's added at each stage.

## Architecture Evolution

```
Stage 1:
┌─────────────────┐
│  Dice Roller    │──→ Prometheus
│   (FastAPI)     │──→ Loki (via Alloy)
│                 │──→ Tempo (via OTel Collector)
└─────────────────┘

Stage 2:
┌─────────────────┐      ┌─────────────────┐
│   Streamlit     │─────→│  Dice Roller    │──→ Prometheus
│   Frontend      │      │   (FastAPI)     │──→ Loki
└─────────────────┘      └─────────────────┘──→ Tempo
        │                                            ↑
        └────────────────────────────────────────────┘
                  (trace context propagation)

Stage 3:
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Streamlit     │─────→│  Dice Roller    │─────→│  Die Service    │
│   Frontend      │      │   (FastAPI)     │      │   (FastAPI)     │
└─────────────────┘      └─────────────────┘      └─────────────────┘
        │                         │                         │
        └─────────────────────────┴─────────────────────────┘
                    (distributed trace across 3 services)

Stage 4:
Same as Stage 3, but Dice Roller now has async endpoint with concurrent operations

Stage 5:
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   Streamlit     │─────→│  Dice Roller    │─────→│  Die Service    │
│   Frontend      │      │   (FastAPI)     │      │   (FastAPI)     │
└─────────────────┘      └─────────────────┘      └────────┬────────┘
                                                            │
                                                            ↓
                                                   ┌─────────────────┐
                                                   │   PostgreSQL    │
                                                   │                 │
                                                   └─────────────────┘

Stage 6:
Same as Stage 5, but with advanced log routing:
- Usage logs → separate destination
- Operational logs → main Loki
```

## Feature Matrix

| Feature | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 |
|---------|---------|---------|---------|---------|---------|---------|
| **Services** |
| Dice Roller API | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Streamlit Frontend | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Die Service | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| PostgreSQL | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Endpoints** |
| GET /roll | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| GET /roll-async | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| GET /dice | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Observability - Metrics** |
| Automatic HTTP metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Custom business metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service-to-service metrics | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Database metrics | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Async operation metrics | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Observability - Logs** |
| Structured JSON logs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trace context in logs | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Log aggregation (Loki) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Selective log routing | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Usage tracking logs | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Observability - Traces** |
| Automatic instrumentation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Trace context propagation | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Distributed traces | ❌ | ✅ (2 svcs) | ✅ (3 svcs) | ✅ (3 svcs) | ✅ (3 svcs + DB) | ✅ |
| Parent/child spans | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Concurrent operation traces | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Database query spans | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Grafana Dashboards** |
| Request rate panels | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Latency percentiles | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Error rate tracking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Service dependency viz | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Database metrics panels | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Usage analytics panels | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Testing & Traffic Gen** |
| Basic traffic generation | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-service traffic | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Performance testing | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Resilience testing | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |

## Metrics Evolution

### Stage 1 Metrics
```python
# Automatic (via prometheus-fastapi-instrumentator)
http_requests_total
http_request_duration_seconds

# Custom
dice_rolls_total{die_type, result}
dice_roll_value{die_type}
```

### Stage 2 Metrics (Added)
```python
# Frontend
streamlit_button_clicks_total{die_type}
streamlit_requests_total{die_type, status_code}
streamlit_request_duration_seconds{die_type}
```

### Stage 3 Metrics (Added)
```python
# Die Service
die_specifications_requested_total{identifier}
die_list_requests_total
die_specifications_loaded

# Dice Roller (added)
die_service_requests_total{identifier, status}
die_service_request_duration_seconds
```

### Stage 4 Metrics (Added)
```python
# Dice Roller async
async_rolls_total{die_type, result}
async_roll_batch_size
async_roll_duration_seconds
async_rolls_in_progress

# Frontend (added)
async_roll_requests_total{batch_size}
```

### Stage 5 Metrics (Added)
```python
# Die Service database
database_queries_total{query_type, result}
database_query_duration_seconds{query_type}
database_connection_pool_size
database_connection_pool_available

# PostgreSQL (via postgres_exporter)
pg_stat_database_numbackends
pg_stat_activity_count
pg_database_size_bytes
```

### Stage 6 Metrics
No new metrics, but usage logs can be aggregated for analytics

## Trace Span Structure Evolution

### Stage 1: Single Service
```
HTTP GET /roll
└─ (automatic FastAPI span)
```

### Stage 2: Two Services
```
HTTP GET (Frontend)
├─ Button click span
└─ HTTP GET /roll (Backend)
   └─ (automatic FastAPI span)
```

### Stage 3: Three Services
```
HTTP GET (Frontend)
├─ Button click span
└─ HTTP GET /roll (Dice Roller)
   ├─ (automatic FastAPI span)
   └─ HTTP GET /dice (Die Service)
      └─ (automatic FastAPI span)
```

### Stage 4: With Async Operations
```
HTTP GET /roll-async (Dice Roller)
├─ (automatic FastAPI span)
├─ Query die service
│  └─ HTTP GET /dice
└─ Async roll batch (parent)
   ├─ Roll 1 (child, concurrent)
   ├─ Roll 2 (child, concurrent)
   ├─ Roll 3 (child, concurrent)
   └─ ... (N children running in parallel)
```

### Stage 5: With Database
```
HTTP GET (Frontend)
├─ Button click span
└─ HTTP GET /roll (Dice Roller)
   ├─ (automatic FastAPI span)
   └─ HTTP GET /dice (Die Service)
      ├─ (automatic FastAPI span)
      └─ SELECT query (PostgreSQL)
         └─ (automatic DB span with SQL statement)
```

### Stage 6: Usage Tracking
Same trace structure as Stage 5, but logs are routed based on content

## Log Fields Evolution

### Stage 1 Log Fields
```json
{
  "timestamp": "2025-10-12T10:30:00Z",
  "level": "INFO",
  "message": "Roll completed",
  "logger": "dice-roller",
  "trace_id": "abc123...",
  "span_id": "def456...",
  "die_type": "fair",
  "roll_value": 5
}
```

### Stage 2 Log Fields (Added)
```json
{
  // ... existing fields ...
  "backend_status": 200,
  "backend_url": "http://dice-roller:8000/roll"
}
```

### Stage 3 Log Fields (Added)
```json
{
  // ... existing fields ...
  "die_identifier": "risky",
  "die_found": true
}
```

### Stage 4 Log Fields (Added)
```json
{
  // ... existing fields ...
  "async_batch_size": 10,
  "async_roll_index": 3,
  "async_total_result": 42
}
```

### Stage 5 Log Fields (Added)
```json
{
  // ... existing fields ...
  "db_query_type": "get",
  "db_query_duration_ms": 12.5,
  "db_result_count": 1
}
```

### Stage 6 Log Fields (Added)
```json
{
  // ... existing fields ...
  "usage": true,
  "event_type": "sign_in",
  "session_id": "uuid-here",
  "username": "alice"
}
```

## Dashboard Panel Count Growth

| Stage | Panels | Categories |
|-------|--------|------------|
| 1 | 12 | HTTP metrics, Latency, Roll distribution, Logs, Traces |
| 2 | 18 | + Frontend metrics, E2E latency, Service deps |
| 3 | 26 | + Die service metrics, Service-to-service, Multi-service traces |
| 4 | 32 | + Async metrics, Performance comparison, Concurrency viz |
| 5 | 42 | + Database metrics, DB operations, DB query viz, Health |
| 6 | 46 | + Usage analytics, Event tracking, Log routing viz |

## Complexity Metrics

| Metric | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 |
|--------|---------|---------|---------|---------|---------|---------|
| Total Services | 1 | 2 | 3 | 3 | 4 | 4 |
| Unique Endpoints | 1 | 1 | 2 | 3 | 3 | 3 |
| Custom Metrics | 2 | 5 | 8 | 12 | 16 | 16 |
| Max Trace Depth | 1 | 2 | 3 | 3 | 4 | 4 |
| Max Concurrent Spans | 1 | 1 | 1 | 10+ | 10+ | 10+ |
| Docker Containers | 1 | 2 | 3 | 3 | 5 | 5 |
| Dashboard Panels | 12 | 18 | 26 | 32 | 42 | 46 |

## Implementation Time Estimates

Based on complexity and assuming familiarity with tools:

| Stage | Estimated Time | Cumulative |
|-------|----------------|------------|
| 1 | 4-6 hours | 4-6 hours |
| 2 | 3-4 hours | 7-10 hours |
| 3 | 3-4 hours | 10-14 hours |
| 4 | 2-3 hours | 12-17 hours |
| 5 | 4-5 hours | 16-22 hours |
| 6 | 2-3 hours | 18-25 hours |

**Total: 18-25 hours** for complete implementation

Breakdown per stage:
- Application code: 30-40%
- Instrumentation: 25-35%
- Dashboard creation: 20-25%
- Testing and debugging: 15-20%

## Learning Progression

| Stage | Primary Learning Goal | Secondary Concepts |
|-------|----------------------|-------------------|
| 1 | Basic O11y setup | Automatic instrumentation, JSON logging |
| 2 | Distributed tracing | Trace propagation, W3C standard |
| 3 | Multi-hop traces | Service maps, complex dependencies |
| 4 | Async operations | Parent/child spans, concurrency |
| 5 | Database observability | Auto-instrumentation limits, SQL spans |
| 6 | Advanced log routing | Content-based routing, analytics |

## Recommended Focus Areas

### Stage 1
**Master these before moving on:**
- Understanding Prometheus metric types (Counter, Histogram)
- JSON structured logging format
- Reading traces in Grafana Tempo
- Basic PromQL queries

### Stage 2
**Master these before moving on:**
- W3C Trace Context format
- HTTP header-based context propagation
- Understanding distributed trace waterfalls
- Service dependency visualization

### Stage 3
**Master these before moving on:**
- Multi-service trace analysis
- Identifying bottlenecks in trace waterfalls
- Service-to-service metrics patterns
- Complex LogQL queries

### Stage 4
**Master these before moving on:**
- Parent/child span relationships
- Interpreting concurrent/overlapping spans
- Performance comparison methodologies
- Async instrumentation patterns

### Stage 5
**Master these before moving on:**
- Database span interpretation
- Connection pool monitoring
- Identifying slow queries in traces
- Database resilience testing

### Stage 6
**Master these before moving on:**
- Alloy filtering and routing
- Separating operational vs. business metrics
- Usage analytics patterns
- Multi-destination log routing

## Next Steps After Completion

Once you've completed all 6 stages:

1. **Add Alerting**: Create Prometheus alerting rules for each stage
2. **Implement SLOs**: Define Service Level Objectives and track them
3. **Chaos Engineering**: Test observability under failure scenarios
4. **Scale Testing**: See how observability performs under high load
5. **Cost Optimization**: Analyze observability data volume and optimize
6. **Custom Exporters**: Build custom Prometheus exporters for specific metrics
7. **Advanced Dashboards**: Create executive-level dashboards with SLOs
8. **Documentation**: Write runbooks based on observability data
