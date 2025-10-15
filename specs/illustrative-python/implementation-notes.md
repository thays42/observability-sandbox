# Implementation Notes

## Overview

This document provides practical implementation guidance for the progressive Python demo described in `overview.md`.

## Key Implementation Patterns

### OpenTelemetry Setup Pattern (Python)

For each FastAPI service, use this boilerplate:

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize tracing
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint="http://alloy:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

# Create FastAPI app
app = FastAPI()

# Instrument FastAPI (automatic trace creation for HTTP requests)
FastAPIInstrumentor.instrument_app(app)
```

### JSON Logging Pattern

```python
import logging
import json
from opentelemetry import trace

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        
        # Add trace context
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_data["trace_id"] = format(ctx.trace_id, "032x")
            log_data["span_id"] = format(ctx.span_id, "016x")
        
        # Add any extra fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
            
        return json.dumps(log_data)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage with extra fields:
logger.info("Roll completed", extra={'extra_fields': {'die_type': 'fair', 'roll_value': 5}})
```

### Custom Prometheus Metrics Pattern

```python
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
dice_rolls = Counter(
    'dice_rolls_total',
    'Total number of dice rolls',
    ['die_type', 'result']  # Labels
)

roll_values = Histogram(
    'dice_roll_value',
    'Distribution of roll values',
    ['die_type'],
    buckets=[1, 2, 3, 4, 5, 6, 7]  # Custom buckets for dice
)

# Usage
dice_rolls.labels(die_type='fair', result='success').inc()
roll_values.labels(die_type='fair').observe(5)
```

### Custom Span Attributes Pattern

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

# Get current span and add attributes
span = trace.get_current_span()
span.set_attribute("die.type", "fair")
span.set_attribute("die.result", 5)

# Or create a new span with attributes
with tracer.start_as_current_span("roll_die") as span:
    span.set_attribute("die.type", "risky")
    result = roll_die()
    span.set_attribute("die.result", result)
```

### Trace Context Propagation (HTTP)

```python
import requests
from opentelemetry import trace
from opentelemetry.propagate import inject

# Client side (e.g., Streamlit or dice-roller calling die-service)
headers = {}
inject(headers)  # Injects W3C Trace Context headers
response = requests.get("http://die-service/dice", headers=headers)

# Server side (FastAPI) - automatic with FastAPIInstrumentor
# No additional code needed - trace context extracted automatically
```

## Docker Compose Structure Recommendations

### Directory Layout

```
specs/illustrative-python/
├── stage1/
│   ├── docker-compose.yml
│   ├── dice-roller/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   ├── traffic-gen/
│   │   ├── generate_traffic.py
│   │   └── pyproject.toml
│   └── grafana-dashboards/
│       └── stage1-dashboard.json
├── stage2/
│   ├── docker-compose.yml (extends stage1)
│   ├── streamlit-frontend/
│   │   ├── Dockerfile
│   │   ├── app.py
│   │   └── pyproject.toml
│   └── grafana-dashboards/
│       └── stage2-dashboard.json
├── stage3/
│   └── ...
```

### Docker Compose Pattern

Each stage should:
1. Define a `monitoring` network (external, created by main stack)
2. Include necessary services for that stage
3. Mount service code as volumes for development
4. Set appropriate environment variables for OTel

Example `docker-compose.yml` for Stage 1:

```yaml
version: '3.8'

networks:
  monitoring:
    external: true

services:
  dice-roller:
    build: ./dice-roller
    container_name: dice-roller-stage1
    ports:
      - "8100:8000"
    environment:
      - OTEL_SERVICE_NAME=dice-roller
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://alloy:4318
      - OTEL_TRACES_EXPORTER=otlp
      - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
    networks:
      - monitoring
    labels:
      com.docker.compose.project: "stage1-dice-roller"
      com.docker.compose.service: "dice-roller"
```

## Alloy Configuration Updates

For each stage, update `stack/alloy/config.alloy` to include new services:

```alloy
discovery.relabel "demo_apps" {
  // ...
  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
    regex         = "(dice-roller|shiny-curl-gui|stage1-dice-roller|stage2-.*|stage3-.*)"
    action        = "keep"
  }
}
```

## Prometheus Scrape Configuration

Add scrape targets for each stage's services in `stack/prometheus/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'dice-roller-stage1'
    static_configs:
      - targets: ['dice-roller-stage1:8000']
  
  - job_name: 'streamlit-frontend-stage2'
    static_configs:
      - targets: ['streamlit-frontend-stage2:8501']
```

## Traffic Generation Script Pattern

All traffic generation scripts should follow this structure:

```python
import asyncio
import httpx
import random
import logging
from datetime import datetime

# Configuration
NUM_USERS = 10
MAX_ROLLS_PER_USER = 20
BASE_URL = "http://localhost:8100"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def simulate_user(user_id: int, num_rolls: int):
    async with httpx.AsyncClient() as client:
        for roll_num in range(num_rolls):
            die_type = random.choice(["fair", "risky"])
            try:
                response = await client.get(f"{BASE_URL}/roll?die={die_type}")
                logging.info(f"User {user_id} roll {roll_num+1}/{num_rolls}: {die_type} -> {response.status_code}")
            except Exception as e:
                logging.error(f"User {user_id} roll {roll_num+1}/{num_rolls} failed: {e}")
            
            await asyncio.sleep(random.uniform(0.5, 2.0))  # Think time
    
    logging.info(f"User {user_id} finished all {num_rolls} rolls")

async def main():
    logging.info(f"Starting traffic generation: {NUM_USERS} users")
    
    # Create user tasks
    tasks = []
    for user_id in range(1, NUM_USERS + 1):
        num_rolls = random.randint(1, MAX_ROLLS_PER_USER)
        tasks.append(simulate_user(user_id, num_rolls))
    
    await asyncio.gather(*tasks)
    logging.info("Traffic generation complete")

if __name__ == "__main__":
    asyncio.run(main())
```

## Testing Each Stage

For each stage, follow this checklist:

1. **Build and start services:**
   ```bash
   cd specs/illustrative-python/stageN
   docker compose up -d
   ```

2. **Verify services are healthy:**
   ```bash
   curl http://localhost:8100/  # Or appropriate port
   curl http://localhost:8100/metrics
   ```

3. **Check logs are being collected:**
   ```bash
   curl 'http://localhost:3100/loki/api/v1/query_range' \
     --get --data-urlencode 'query={container_name="dice-roller-stage1"}'
   ```

4. **Verify traces are being collected:**
   - Navigate to Grafana Explore → Tempo
   - Search by service name
   - Verify traces appear

5. **Run traffic generation:**
   ```bash
   cd traffic-gen
   python generate_traffic.py
   ```

6. **Verify metrics in Prometheus:**
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=dice_rolls_total'
   ```

7. **Check dashboard:**
   - Navigate to Grafana → Dashboards
   - Verify panels are populated with data

8. **Test trace-to-logs correlation:**
   - Find a trace in Tempo
   - Click "Logs for this span"
   - Verify logs appear in Loki with correct trace_id

## Common Pitfalls and Solutions

### Issue: Traces not appearing in Tempo

**Solution:**
- Check OTel Collector logs: `docker compose --project-directory stack logs otel-collector`
- Verify OTLP endpoint is reachable from service container
- Ensure `OTEL_TRACES_EXPORTER=otlp` is set
- Check that auto-instrumentation is installed: `opentelemetry-instrumentation-fastapi`

### Issue: Logs missing trace_id

**Solution:**
- Verify span is active when logging
- Ensure JSONFormatter gets span context: `trace.get_current_span()`
- Check that tracer is initialized before logging

### Issue: Metrics not scraped by Prometheus

**Solution:**
- Verify service is on `monitoring` network
- Check Prometheus targets page: http://localhost:9090/targets
- Ensure `/metrics` endpoint is accessible: `curl http://service:port/metrics`
- Verify scrape config in `prometheus.yml`

### Issue: Alloy not collecting logs

**Solution:**
- Check Alloy UI: http://localhost:12345
- Verify container labels match Alloy filter regex
- Check Alloy logs: `docker compose --project-directory stack logs alloy`
- Test Loki is receiving logs: `curl http://localhost:3100/ready`

## Stage 6 Implementation Details

Stage 6 adds usage tracking by routing specific logs to a different destination. Implementation approach:

### Alloy Configuration for Usage Logs

Add a second Loki write endpoint for usage logs:

```alloy
loki.process "demo_apps" {
  forward_to = [loki.process.usage_filter.receiver]
  
  // ... existing JSON parsing stages ...
}

// Filter usage logs
loki.process "usage_filter" {
  forward_to = [loki.write.local.receiver, loki.write.usage.receiver]
  
  // Only forward logs with usage=true to usage endpoint
  stage.match {
    selector = "{container_name=~\"streamlit-frontend.*\"} |= `\"usage\":true`"
    
    // Forward to usage logs
    stage.output {
      source = "usage"
    }
  }
  
  // Forward all logs to main Loki
  stage.output {
    source = "local"
  }
}

// Write to main Loki
loki.write "local" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}

// Write usage logs to separate location (could be different Loki, file, or cloud service)
loki.write "usage" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
    // In production, this might be a different URL
    // Or even a different sink (e.g., S3, BigQuery)
  }
}
```

### Streamlit Usage Logging

```python
import uuid
import logging

# Generate session ID
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# Usage log helper
def log_usage_event(event_type: str, **kwargs):
    logger.info(
        f"Usage event: {event_type}",
        extra={
            'extra_fields': {
                'usage': True,
                'event_type': event_type,
                'session_id': st.session_state.session_id,
                'username': st.session_state.get('username', 'anonymous'),
                **kwargs
            }
        }
    )

# Sign-in event
username = st.text_input("Username")
if st.button("Sign In"):
    st.session_state.username = username
    log_usage_event('sign_in', username=username)

# Run event
if st.button("Run"):
    log_usage_event('run', die_type=selected_die)
    # ... existing roll logic ...
```

## Performance Considerations

1. **OTel Batch Processing:** Configure batch span processor for better performance
2. **Database Connection Pooling:** Use connection pools (Stage 5) to reduce overhead
3. **Metric Cardinality:** Be careful with label combinations - keep cardinality low
4. **Log Volume:** In production, consider sampling high-volume logs
5. **Trace Sampling:** For high-traffic services, implement trace sampling

## Next Steps After Completing Stages

Once all stages are implemented, consider:

1. **Alerting:** Add Prometheus alerting rules for error rates, latency thresholds
2. **SLOs:** Define and monitor Service Level Objectives
3. **Chaos Engineering:** Introduce failures (network delays, service crashes) to test observability
4. **Performance Testing:** Use locust or k6 for realistic load testing
5. **Production Readiness:** Add health checks, graceful shutdown, resource limits
