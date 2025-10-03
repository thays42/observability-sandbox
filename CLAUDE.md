# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an observability stack built with Docker Compose, consisting of Prometheus for metrics collection, Loki for log aggregation, and Grafana for visualization. The stack is designed for monitoring applications and infrastructure.

## Architecture

The stack consists of five main services running in Docker containers:

- **Prometheus**: Metrics collection and storage (port 9090)
  - Configuration: [prometheus/prometheus.yml](prometheus/prometheus.yml)
  - Data persisted in `prometheus-data` volume
  - Scrapes itself and demo-fastapi-rolldice every 15 seconds by default

- **Loki**: Log aggregation and storage (port 3100)
  - Configuration: [loki/loki-config.yml](loki/loki-config.yml)
  - Data persisted in `loki-data` volume
  - Receives logs from all containers via Docker Loki logging driver
  - Retention: 744 hours (31 days)

- **Grafana**: Metrics and logs visualization (port 3000)
  - Configuration: [grafana/grafana.ini](grafana/grafana.ini)
  - Datasource provisioning: [grafana/provisioning/datasources/](grafana/provisioning/datasources/)
  - Data persisted in `grafana-data` volume
  - Pre-configured with Prometheus (default) and Loki datasources
  - Anonymous viewing enabled, admin credentials: admin/admin

- **demo-fastapi-rolldice**: Demo FastAPI application (port 8001)
  - Source: [apps/dice-roller/](apps/dice-roller/)
  - Python 3.13 managed with uv
  - Provides `/roll/{dice}` endpoint (e.g., `/roll/3d6`)
  - Exposes Prometheus metrics at `/metrics` using prometheus-fastapi-instrumentator

- **shiny-curl-gui**: Demo R Shiny application (port 8002)
  - Source: [apps/shiny-curl-gui/](apps/shiny-curl-gui/)
  - R 4.5.1 (rocker/r-ver base image) with httr2 for HTTP requests, logger for JSON logging
  - GUI for making HTTP requests (GET, POST, PUT, DELETE)
  - Displays formatted response with status code, headers, and body
  - Uses binary packages from Posit Package Manager for faster builds on ARM
  - Structured JSON logging with session tracking (UUID-based)
  - Logs: INFO (app start, sessions), DEBUG (requests), INFO/WARN/ERROR (responses by status code)
  - TODO: Add request body and custom headers support

All services communicate via the `monitoring` Docker network.

## Common Commands

### Starting the Stack
```bash
docker compose up -d
```

### Stopping the Stack
```bash
docker compose down
```

### Viewing Logs
```bash
# All services (via Docker)
docker compose logs -f

# Specific service (via Docker)
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f loki
docker compose logs -f demo-fastapi-rolldice
docker compose logs -f shiny-curl-gui

# Query logs via Loki (all containers send logs to Loki)
# Use Grafana Explore with Loki datasource or query directly:
curl 'http://localhost:3100/loki/api/v1/query_range' \
  --get --data-urlencode 'query={container_name="shiny-curl-gui"}'
```

### Restarting After Configuration Changes
```bash
# Prometheus configuration
docker compose restart prometheus

# Loki configuration
docker compose restart loki

# Grafana configuration
docker compose restart grafana
```

### Accessing Services
- Prometheus UI: http://localhost:9090
- Loki API: http://localhost:3100 (ready check at http://localhost:3100/ready)
- Grafana UI: http://localhost:3000 (includes Loki Explore for log queries)
- Demo Dice Roller API: http://localhost:8001 (metrics at http://localhost:8001/metrics)
- Shiny cURL GUI: http://localhost:8002

## Configuration Structure

### Prometheus
- Global scrape and evaluation interval: 15s
- Add new scrape targets in [prometheus/prometheus.yml](prometheus/prometheus.yml) under `scrape_configs`
- Configuration is mounted read-only from host

### Loki
- All containers send logs to Loki via Docker Loki logging driver
- Logs queryable by labels: `container_name`, `job`, `compose_project`, `compose_service`
- Configuration in [loki/loki-config.yml](loki/loki-config.yml)
- 31-day retention period
- IMPORTANT: Uses `host.docker.internal:3100` in logging driver config (not container network)

### Grafana
- Datasources are provisioned automatically from [grafana/provisioning/datasources/](grafana/provisioning/datasources/)
- To add dashboards, create a dashboard provisioning file in `grafana/provisioning/dashboards/`
- Custom Grafana settings in [grafana/grafana.ini](grafana/grafana.ini)
- Query logs in Explore → Loki datasource → `{container_name="shiny-curl-gui"}`

## Adding New Monitoring Targets

To monitor a new application or service:

1. **For metrics**: Add the target to [prometheus/prometheus.yml](prometheus/prometheus.yml) under `scrape_configs`:
```yaml
- job_name: 'my-app'
  static_configs:
    - targets: ['my-app:8080']
```

2. **For logs**: Add Loki logging driver to the service in [docker-compose.yml](docker-compose.yml):
```yaml
my-app:
  logging:
    driver: loki
    options:
      loki-url: "http://host.docker.internal:3100/loki/api/v1/push"
      loki-external-labels: "job=my-app,container_name=my-app"
```

3. Add the service to the `monitoring` network in [docker-compose.yml](docker-compose.yml)

4. Restart services: `docker compose up -d` and `docker compose restart prometheus`

## User Preferences

### Communication Style
- Be very concise when summarizing what you will do or have done. I will ask you to provide more detail if I want it.
