# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is an observability stack built with Docker Compose, consisting of Prometheus for metrics collection and Grafana for visualization. The stack is designed for monitoring applications and infrastructure.

## Architecture

The stack consists of four main services running in Docker containers:

- **Prometheus**: Metrics collection and storage (port 9090)
  - Configuration: [prometheus/prometheus.yml](prometheus/prometheus.yml)
  - Data persisted in `prometheus-data` volume
  - Scrapes itself and demo-fastapi-rolldice every 15 seconds by default

- **Grafana**: Metrics visualization and dashboards (port 3000)
  - Configuration: [grafana/grafana.ini](grafana/grafana.ini)
  - Datasource provisioning: [grafana/provisioning/datasources/prometheus.yml](grafana/provisioning/datasources/prometheus.yml)
  - Data persisted in `grafana-data` volume
  - Pre-configured with Prometheus as default datasource
  - Anonymous viewing enabled, admin credentials: admin/admin

- **demo-fastapi-rolldice**: Demo FastAPI application (port 8001)
  - Source: [apps/dice-roller/](apps/dice-roller/)
  - Python 3.13 managed with uv
  - Provides `/roll/{dice}` endpoint (e.g., `/roll/3d6`)
  - Exposes Prometheus metrics at `/metrics` using prometheus-fastapi-instrumentator

- **shiny-curl-gui**: Demo R Shiny application (port 8002)
  - Source: [apps/shiny-curl-gui/](apps/shiny-curl-gui/)
  - R 4.5.1 (rocker/r-ver base image) with httr2 for HTTP requests
  - GUI for making HTTP requests (GET, POST, PUT, DELETE)
  - Displays formatted response with status code, headers, and body
  - Uses binary packages from Posit Package Manager for faster builds on ARM
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
# All services
docker compose logs -f

# Specific service
docker compose logs -f prometheus
docker compose logs -f grafana
docker compose logs -f demo-fastapi-rolldice
docker compose logs -f shiny-curl-gui
```

### Restarting After Configuration Changes
```bash
# Prometheus configuration
docker compose restart prometheus

# Grafana configuration
docker compose restart grafana
```

### Accessing Services
- Prometheus UI: http://localhost:9090
- Grafana UI: http://localhost:3000
- Demo Dice Roller API: http://localhost:8001 (metrics at http://localhost:8001/metrics)
- Shiny cURL GUI: http://localhost:8002

## Configuration Structure

### Prometheus
- Global scrape and evaluation interval: 15s
- Add new scrape targets in [prometheus/prometheus.yml](prometheus/prometheus.yml) under `scrape_configs`
- Configuration is mounted read-only from host

### Grafana
- Datasources are provisioned automatically from [grafana/provisioning/datasources/](grafana/provisioning/datasources/)
- To add dashboards, create a dashboard provisioning file in `grafana/provisioning/dashboards/`
- Custom Grafana settings in [grafana/grafana.ini](grafana/grafana.ini)

## Adding New Monitoring Targets

To monitor a new application or service:

1. Add the target to [prometheus/prometheus.yml](prometheus/prometheus.yml) under `scrape_configs`:
```yaml
- job_name: 'my-app'
  static_configs:
    - targets: ['my-app:8080']
```

2. If the target is a Docker container, add it to the `monitoring` network in [docker-compose.yml](docker-compose.yml)

3. Restart Prometheus: `docker compose restart prometheus`

## User Preferences

### Communication Style
- Be very concise when summarizing what you will do or have done. I will ask you to provide more detail if I want it.
