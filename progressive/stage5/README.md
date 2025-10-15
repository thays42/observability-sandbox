# Stage 5: Database Backend

## Overview

Stage 5 adds PostgreSQL as a database backend for the die-service, replacing in-memory storage. This stage demonstrates:

- Database instrumentation with OpenTelemetry (automatic SQL query tracing)
- Database-specific metrics (query performance, connection pool monitoring)
- Database observability integration (postgres_exporter)
- Full distributed tracing through database layer
- Database resilience and performance testing

## Architecture

```
Traffic Generator → Frontend → Dice Roller → Die Service → PostgreSQL
                                                    ↓
                                             postgres_exporter → Prometheus
```

**New in Stage 5:**
- PostgreSQL database for die specifications storage
- postgres_exporter for database-level metrics
- asyncpg with OpenTelemetry instrumentation
- Database connection pooling
- Enhanced database logging and metrics

## Services

| Service | Port | Description |
|---------|------|-------------|
| postgres | 5432 | PostgreSQL 16 database |
| postgres-exporter | 9187 | PostgreSQL metrics exporter |
| die-service | 8109 | Die specifications API (with database backend) |
| dice-roller | 8110 | Dice rolling API |
| frontend | 8111 | Frontend API |

## Prerequisites

1. **Observability stack running:**
   ```bash
   cd /home/thays/Projects/observability/observability-sandbox
   docker compose --project-directory stack up -d
   ```

2. **Monitoring network created:**
   ```bash
   docker network create monitoring
   ```

3. **Stack services updated:**
   - Alloy configured to collect logs from stage5 services
   - Prometheus configured to scrape stage5 services and postgres_exporter

## Quick Start

### 1. Start Stage 5 Services

```bash
cd progressive/stage5
docker compose up -d
```

### 2. Verify Services

```bash
# Check all services are running
docker compose ps

# Check database is healthy
docker compose logs postgres | grep "database system is ready"

# Check die-service connected to database
docker compose logs die-service | grep "Database connection pool established"

# Test endpoints
curl http://localhost:8109/                    # Die service info
curl http://localhost:8109/dice                 # List all die
curl http://localhost:8109/dice?identifier=fair # Get fair die spec
curl http://localhost:8110/roll?die=fair        # Roll fair die
curl http://localhost:8111/roll?die=risky       # Roll via frontend
```

### 3. Generate Traffic

```bash
cd traffic-gen

# Install dependencies (first time only)
uv venv
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
uv pip install -e .

# Run traffic generation
python generate_traffic.py

# Optional: Run database load test
python test-database-load.py
```

### 4. View in Grafana

Open http://localhost:3000 and navigate to:
- **Dashboards → Stage 5 Dashboard** - Pre-built dashboard with all metrics
- **Explore → Tempo** - Search for distributed traces
- **Explore → Loki** - Query logs

## Key Features

### Database Integration

**Schema:**
```sql
CREATE TABLE die_specifications (
    identifier VARCHAR(50) PRIMARY KEY,
    faces INTEGER[] NOT NULL,
    error_rate FLOAT NOT NULL
);
```

**Data:**
- `fair`: [1,2,3,4,5,6], error_rate=0.0
- `risky`: [2,3,4,5,6,7], error_rate=0.1
- `extreme`: [0,0,6,6,6,6], error_rate=0.5

### Database Observability

**Metrics (from die-service):**
- `database_queries_total{query_type, result}` - Total database queries
- `database_query_duration_seconds{query_type}` - Query latency histogram
- `database_connection_pool_size` - Connection pool size
- `database_connection_pool_available` - Available connections

**Metrics (from postgres_exporter):**
- `pg_stat_database_numbackends` - Active database connections
- `pg_stat_activity_count` - Active queries
- `pg_database_size_bytes` - Database size

**Tracing:**
- Automatic SQL query spans via `opentelemetry-instrumentation-asyncpg`
- Query parameters sanitized in traces
- Database operations visible in trace waterfall
- Full trace: frontend → dice-roller → die-service → postgres

**Logging:**
- Database connection events (established, failed, closed)
- Query execution with duration and type
- Connection pool warnings
- All logs include trace_id and span_id for correlation

## Verification Checklist

### Services Health

- [ ] All containers running: `docker compose ps`
- [ ] PostgreSQL healthy: Check `docker compose ps postgres` shows "healthy"
- [ ] Die service connected: Check logs for "Database connection pool established"
- [ ] Metrics exposed: `curl http://localhost:8109/metrics | grep database_`
- [ ] PostgreSQL metrics: `curl http://localhost:9187/metrics | grep pg_`

### Observability

- [ ] **Logs in Loki:**
  ```
  {container_name="die-service-stage5"} | json
  {container_name="die-service-stage5"} | json | message =~ ".*[Dd]atabase.*"
  ```

- [ ] **Metrics in Prometheus:**
  ```
  database_queries_total
  database_query_duration_seconds
  pg_stat_database_numbackends{datname="dicedb"}
  ```

- [ ] **Traces in Tempo:**
  - Search by service: `service.name="die-service"`
  - Look for database spans with `db.system="postgresql"`
  - Verify SQL statements visible in span attributes

- [ ] **Trace-to-logs correlation:**
  - Click on a database span in Tempo
  - Click "Logs for this span"
  - Verify logs appear with matching trace_id

### Dashboard

- [ ] Stage 5 Dashboard shows data in all panels
- [ ] Database query metrics visible
- [ ] Connection pool metrics updating
- [ ] PostgreSQL metrics from postgres_exporter

### Traffic Generation

- [ ] `generate_traffic.py` runs without errors
- [ ] See distributed traces through all 4 layers (frontend → dice-roller → die-service → postgres)
- [ ] Database load test (`test-database-load.py`) completes successfully

## Common Queries

### Prometheus (Metrics)

```promql
# Database query rate
rate(database_queries_total[1m])

# Database query latency P95
histogram_quantile(0.95, rate(database_query_duration_seconds_bucket[5m]))

# Connection pool usage
database_connection_pool_size - database_connection_pool_available

# PostgreSQL active connections
pg_stat_database_numbackends{datname="dicedb"}
```

### Loki (Logs)

```logql
# All die-service logs
{container_name="die-service-stage5"} | json

# Database-related logs
{container_name="die-service-stage5"} | json | message =~ ".*[Dd]atabase.*"

# Database errors
{container_name="die-service-stage5"} | json | level="ERROR" | message =~ ".*query.*"

# Logs for a specific trace
{container_name="die-service-stage5"} | json | trace_id="<your-trace-id>"
```

### Tempo (Traces)

```
# Search by service
service.name="die-service"

# Search for traces with database operations
span.db.system="postgresql"

# Search by duration (slow queries)
duration > 100ms
```

## Testing Database Performance

### Load Testing

The `test-database-load.py` script generates high-volume queries to test database performance:

```bash
cd traffic-gen
python test-database-load.py
```

**Configuration** (edit script to customize):
- `QUERIES_PER_SECOND = 50` - Target query rate
- `DURATION_SECONDS = 30` - Test duration
- `LIST_TO_GET_RATIO = 0.1` - Ratio of list vs get queries

**Metrics to watch:**
- Query latency percentiles (P50, P95, P99)
- Connection pool saturation
- Database CPU and memory usage
- Error rate

## Troubleshooting

### Database Connection Issues

**Symptom:** Die service can't connect to database

**Solutions:**
```bash
# Check PostgreSQL is running
docker compose ps postgres

# Check PostgreSQL logs
docker compose logs postgres

# Verify database credentials
docker compose exec postgres psql -U diceuser -d dicedb -c "\dt"

# Check healthcheck
docker compose exec postgres pg_isready -U diceuser -d dicedb
```

### Missing Database Traces

**Symptom:** No database spans in Tempo

**Solutions:**
- Verify `asyncpg` and `opentelemetry-instrumentation-asyncpg` are installed
- Check die-service logs for instrumentation errors
- Ensure `AsyncPGInstrumentor().instrument()` is called before database operations
- Verify Alloy/OTel Collector is receiving traces

### Slow Queries

**Symptom:** High database query latency

**Solutions:**
```bash
# Check database load
docker compose exec postgres psql -U diceuser -d dicedb -c "SELECT * FROM pg_stat_activity;"

# Check connection pool exhaustion
curl http://localhost:8109/metrics | grep connection_pool

# Review query patterns in Tempo
# Look for slow database spans

# Check PostgreSQL logs for slow queries
docker compose logs postgres | grep "duration:"
```

## Cleanup

```bash
# Stop services
docker compose down

# Remove volumes (deletes database data)
docker compose down -v

# Remove images
docker compose down --rmi all
```

## Next Steps

- **Stage 6:** Add usage tracking with selective log routing
- Implement alerting rules for database errors
- Add SLOs for database query latency

## Resources

- [OpenTelemetry Python AsyncPG Instrumentation](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/asyncpg/asyncpg.html)
- [PostgreSQL Monitoring](https://www.postgresql.org/docs/current/monitoring.html)
- [postgres_exporter Metrics](https://github.com/prometheus-community/postgres_exporter)
- [Stage 5 Specification](../../specs/illustrative-python/overview.md#stage-5-die-database)
