# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an observability stack built with Docker Compose, consisting of Prometheus for metrics collection, Loki for log aggregation, and Grafana for visualization. The stack is designed for monitoring applications and infrastructure.

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
  - Receives logs from all containers via Docker Loki logging driver
  - Retention: 744 hours (31 days)

- **Grafana**: Metrics and logs visualization (port 3000)
  - Configuration: [stack/grafana/grafana.ini](stack/grafana/grafana.ini)
  - Datasource provisioning: [stack/grafana/provisioning/datasources/](stack/grafana/provisioning/datasources/)
  - Data persisted in `stack_grafana-data` volume
  - Pre-configured with Prometheus (default) and Loki datasources
  - Anonymous viewing enabled, admin credentials: admin/admin

### Demo Applications

- **dice-roller**: Demo FastAPI application (port 8001)
  - Source: [dice-roller/](dice-roller/)
  - Compose file: [dice-roller/docker-compose.yml](dice-roller/docker-compose.yml)
  - Python 3.13 managed with uv
  - Provides `/roll/{dice}` endpoint (e.g., `/roll/3d6`)
  - Exposes Prometheus metrics at `/metrics` using prometheus-fastapi-instrumentator

- **shiny-curl-gui**: Demo R Shiny application (port 8002)
  - Source: [shiny-curl-gui/](shiny-curl-gui/)
  - Compose file: [shiny-curl-gui/docker-compose.yml](shiny-curl-gui/docker-compose.yml)
  - R 4.5.1 (rocker/r-ver base image) with httr2 for HTTP requests, logger for JSON logging
  - GUI for making HTTP requests (GET, POST, PUT, DELETE)
  - Displays formatted response with status code, headers, and body
  - Uses binary packages from Posit Package Manager for faster builds on ARM
  - Structured JSON logging with session tracking (UUID-based)
  - Logs: INFO (app start, sessions), DEBUG (requests), INFO/WARN/ERROR (responses by status code)
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
- Grafana UI: http://localhost:3000 (includes Loki Explore for log queries)
- Demo Dice Roller API: http://localhost:8001 (metrics at http://localhost:8001/metrics)
- Shiny cURL GUI: http://localhost:8002

## Configuration Structure

### Prometheus
- Global scrape and evaluation interval: 15s
- Add new scrape targets in [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml) under `scrape_configs`
- Configuration is mounted read-only from host

### Loki
- All containers send logs to Loki via Docker Loki logging driver
- Logs queryable by labels: `container_name`, `job`, `compose_project`, `compose_service`
- Configuration in [stack/loki/loki-config.yml](stack/loki/loki-config.yml)
- 31-day retention period
- IMPORTANT: Uses `host.docker.internal:3100` in logging driver config (not container network)

### Grafana
- Datasources are provisioned automatically from [stack/grafana/provisioning/datasources/](stack/grafana/provisioning/datasources/)
- To add dashboards, create a dashboard provisioning file in `stack/grafana/provisioning/dashboards/`
- Custom Grafana settings in [stack/grafana/grafana.ini](stack/grafana/grafana.ini)
- Query logs in Explore → Loki datasource → `{container_name="shiny-curl-gui"}`

## Adding New Monitoring Targets

To monitor a new application or service:

1. **For metrics**: Add the target to [stack/prometheus/prometheus.yml](stack/prometheus/prometheus.yml) under `scrape_configs`:
```yaml
- job_name: 'my-app'
  static_configs:
    - targets: ['my-app:8080']
```

2. **For logs**: Add Loki logging driver to the service in your docker-compose.yml:
```yaml
my-app:
  logging:
    driver: loki
    options:
      loki-url: "http://host.docker.internal:3100/loki/api/v1/push"
      loki-external-labels: "job=my-app,container_name=my-app"
```

3. Add the service to the `monitoring` network:
```yaml
networks:
  monitoring:
    external: true
```

4. Restart services: `docker compose --project-directory <your-app> up -d` and `docker compose --project-directory stack restart prometheus`

## User Preferences

### Communication Style
- Be very concise when summarizing what you will do or have done. I will ask you to provide more detail if I want it.
