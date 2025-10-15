# Stage 3 Quick Start

## 🚀 Start Stage 3

```bash
cd /Users/thays/Projects/observability/sandbox/specs/illustrative-python/stage3
docker compose up -d
```

## 🔍 Verify Services

```bash
# Check status
docker compose ps

# Test die service
curl http://localhost:8103/dice

# Test dice roller
curl "http://localhost:8104/roll?die=fair"

# Test frontend
curl "http://localhost:8105/roll?die=risky"

# Open UI in browser
open http://localhost:8105
```

## 📊 View Observability Data

### Metrics (Prometheus)
- URL: http://localhost:9090
- Query: `die_specifications_requested_total`
- Query: `rate(die_service_requests_total[1m])`

### Logs (Loki via Grafana)
- URL: http://localhost:3000/explore
- Select: Loki datasource
- Query: `{container_name="die-service-stage3"} | json`
- Query: `{container_name=~".*-stage3"} | json | level="ERROR"`

### Traces (Tempo via Grafana)
- URL: http://localhost:3000/explore
- Select: Tempo datasource
- Search by: `service.name="frontend"`
- View distributed traces across all 3 services

## 🚦 Generate Traffic

```bash
cd traffic-gen
uv pip install -r pyproject.toml
python generate_traffic.py
```

Watch metrics, logs, and traces populate in Grafana!

## 🛑 Stop Services

```bash
docker compose down

# Or with volume cleanup:
docker compose down -v
```

## 📚 More Info

- Full documentation: [README.md](README.md)
- Implementation details: [IMPLEMENTATION-SUMMARY.md](IMPLEMENTATION-SUMMARY.md)
- Project overview: [../README.md](../README.md)

## 🎯 Key URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend UI | http://localhost:8105 | Web interface |
| Frontend API | http://localhost:8105/roll?die=fair | API endpoint |
| Dice Roller | http://localhost:8104/roll?die=fair | Roll API |
| Die Service | http://localhost:8103/dice | List dice |
| Die Service | http://localhost:8103/dice?identifier=fair | Get spec |
| Prometheus | http://localhost:9090 | Metrics |
| Grafana | http://localhost:3000 | Dashboards |
| Alloy | http://localhost:12345 | Log collector UI |

## 🔧 Troubleshooting

**Services won't start:**
```bash
# Check if ports are in use
lsof -i :8103 -i :8104 -i :8105

# Check logs
docker compose logs
```

**No metrics in Prometheus:**
```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Verify metrics endpoint
curl http://localhost:8103/metrics
```

**No logs in Loki:**
```bash
# Check Alloy is running
docker compose --project-directory ../../stack ps alloy

# Check Alloy UI
open http://localhost:12345
```

## ✨ Quick Tests

```bash
# Test 3-service flow
for i in {1..10}; do
  curl -s "http://localhost:8105/roll?die=fair" | jq .roll
  sleep 0.5
done

# Test error handling (risky die)
for i in {1..20}; do
  curl -s "http://localhost:8105/roll?die=risky"
  sleep 0.3
done

# Test unknown die type (should fail gracefully)
curl "http://localhost:8105/roll?die=unknown"
```
