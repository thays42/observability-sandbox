# Stage 1: Single Service Architecture

```mermaid
graph TB
    User[User]

    subgraph "Stage 1 Application"
        DiceRoller[Dice Roller Service<br/>FastAPI :8100<br/>/roll?die=fair|risky]
    end

    subgraph "Observability Stack"
        Alloy[Grafana Alloy]
        Prometheus[Prometheus]
        Loki[Loki]
        Tempo[Tempo]
    end

    User -->|HTTP GET<br/>/roll?die=fair| DiceRoller

    DiceRoller -->|Metrics<br/>/metrics| Prometheus
    DiceRoller -->|Logs<br/>JSON stdout| Alloy
    DiceRoller -->|Traces<br/>OTLP HTTP :4318| Alloy

    Alloy -->|Forward Logs| Loki
    Alloy -->|Forward Traces| Tempo

    style User fill:#e1f5ff
    style DiceRoller fill:#ffe1e1
    style Alloy fill:#fff4e1
    style Prometheus fill:#d0d0d0
    style Loki fill:#d0d0d0
    style Tempo fill:#d0d0d0
```

## Node Roles

### Application Components

- **Dice Roller Service** (:8100): Single FastAPI application
  - **Endpoint**: `GET /roll?die={fair|risky}`
  - **Functionality**: Simulates rolling a 6-sided die with different probability distributions
    - `fair`: Equal probability for all outcomes (1-6)
    - `risky`: Weighted probability (more 1s and 6s)
  - **Metrics**: Exposes `/metrics` endpoint with:
    - HTTP request metrics (duration, count, status codes)
    - Custom counter for dice rolls by die type and outcome
  - **Logs**: JSON-formatted logs to stdout with trace context
    - Fields: timestamp, level, message, trace_id, span_id
  - **Traces**: OpenTelemetry automatic instrumentation
    - Service name: `stage1-dice-roller`
    - Exports to Alloy via OTLP HTTP (port 4318)
    - Creates spans for HTTP requests

### Traffic Flow

1. User makes HTTP GET request to `/roll?die=fair` or `/roll?die=risky`
2. Dice Roller processes request and returns JSON response with roll result
3. **Metrics**: Prometheus scrapes `/metrics` endpoint every 15 seconds
4. **Logs**: Dice Roller writes JSON logs to stdout → Alloy collects → forwards to Loki
5. **Traces**: Dice Roller sends OTLP traces to Alloy → Alloy forwards to Tempo

### Observability Data Generated

- **Metrics**: HTTP request metrics, dice roll counters
- **Logs**: Request/response logs with trace correlation
- **Traces**: Single-span traces for each HTTP request
- **Correlation**: trace_id and span_id in logs enable trace-to-logs navigation in Grafana
