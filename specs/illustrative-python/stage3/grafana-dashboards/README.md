# Stage 3 Grafana Dashboard

## Import Instructions

1. Open Grafana at http://localhost:3000
2. Navigate to Dashboards → New → Import
3. Upload `stage3-dashboard.json` or paste its contents
4. Select Prometheus, Loki, and Tempo datasources when prompted
5. Click Import

## Dashboard Overview

The Stage 3 dashboard extends Stage 2 with panels for the Die Service:

### Row 1: Die Service Metrics
- Die Service request rate
- Die specifications requested by identifier
- Die Service latency (P50, P95, P99)

### Row 2: Service-to-Service Communication
- Dice Roller → Die Service request rate
- Dice Roller → Die Service errors
- Service-to-service latency

### Row 3: Frontend Metrics
- Frontend request rate
- Frontend success rate
- Button clicks by die type

### Row 4: Dice Roller Metrics
- Request rate
- Success rate
- Error rate by die type

### Row 5: Latency Overview
- Request duration percentiles
- Average response time by die type
- End-to-end latency

### Row 6: Roll Distribution
- Rolls by die type
- Roll value distributions

### Row 7: Logs
- Die Service logs
- Dice Roller logs
- Frontend logs
- Error logs

### Row 8: Distributed Tracing
- Instructions for viewing 3-service traces in Tempo
- Service architecture diagram

## Key Queries

### Die Service Metrics
```promql
rate(http_requests_total{job="die-service-stage3"}[1m])
sum by (identifier) (die_specifications_requested_total)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="die-service-stage3"}[5m]))
```

### Service-to-Service
```promql
rate(die_service_requests_total[1m])
rate(die_service_requests_total{status=~"error.*"}[1m])
histogram_quantile(0.95, rate(die_service_request_duration_seconds_bucket[5m]))
```

### Logs
```logql
{container_name="die-service-stage3"} | json
{container_name="dice-roller-stage3"} | json
{container_name="frontend-stage3"} | json
```

## Creating the Dashboard

Since this is a complex dashboard with many panels, it's recommended to:

1. Start with the Stage 2 dashboard as a template
2. Add the new Die Service and Service-to-Service rows
3. Update queries to use stage3 job names
4. Export as JSON and save here

Alternatively, build the dashboard in Grafana UI:
- Add datasources: Prometheus (default), Loki, Tempo
- Create panels following the structure above
- Use the queries listed in this README
- Export via Dashboard Settings → JSON Model
