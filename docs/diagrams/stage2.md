# Stage 2: Frontend + Backend Architecture

```mermaid
graph TB
    User[User]

    subgraph "Stage 2 Application"
        Frontend[Frontend Service<br/>Streamlit :8200<br/>User Interface]
        DiceRoller[Dice Roller Service<br/>FastAPI :8100<br/>/roll?die=fair|risky]
    end

    subgraph "Observability Stack"
        Alloy[Grafana Alloy]
        Prometheus[Prometheus]
        Loki[Loki]
        Tempo[Tempo]
    end

    User -->|HTTP Browse| Frontend
    Frontend -->|HTTP GET<br/>/roll?die=fair| DiceRoller

    Frontend -->|Metrics<br/>/metrics| Prometheus
    Frontend -->|Logs<br/>JSON stdout| Alloy
    Frontend -->|Traces<br/>OTLP HTTP :4318| Alloy

    DiceRoller -->|Metrics<br/>/metrics| Prometheus
    DiceRoller -->|Logs<br/>JSON stdout| Alloy
    DiceRoller -->|Traces<br/>OTLP HTTP :4318| Alloy

    Alloy -->|Forward Logs| Loki
    Alloy -->|Forward Traces| Tempo

    style User fill:#e1f5ff
    style Frontend fill:#ffe1e1
    style DiceRoller fill:#ffe1e1
    style Alloy fill:#fff4e1
    style Prometheus fill:#d0d0d0
    style Loki fill:#d0d0d0
    style Tempo fill:#d0d0d0
```

## Node Roles

### Application Components

- **Frontend Service** (:8200): Streamlit web application
  - **Technology**: Python Streamlit framework
  - **Functionality**: Provides user interface for dice rolling
    - Radio buttons to select die type (fair/risky)
    - Button to trigger roll
    - Display roll results and statistics
  - **Integration**: Makes HTTP requests to Dice Roller Service
  - **Metrics**: Exposes `/metrics` endpoint with HTTP request metrics
  - **Logs**: JSON-formatted logs to stdout with trace context
  - **Traces**: OpenTelemetry automatic instrumentation
    - Service name: `stage2-frontend`
    - Creates spans for user interactions and HTTP client requests
    - Propagates trace context to Dice Roller via HTTP headers

- **Dice Roller Service** (:8100): FastAPI backend service
  - **Endpoint**: `GET /roll?die={fair|risky}`
  - **Functionality**: Simulates rolling dice with different distributions
  - **Metrics**: HTTP request metrics + custom dice roll counters
  - **Logs**: JSON logs with trace context (trace_id, span_id)
  - **Traces**: OpenTelemetry automatic instrumentation
    - Service name: `stage2-dice-roller`
    - Receives trace context from Frontend via HTTP headers
    - Creates child spans under Frontend's trace

### Traffic Flow

1. User interacts with Frontend web interface (selects die type, clicks roll)
2. Frontend creates a trace and makes HTTP request to Dice Roller
3. Dice Roller receives request with trace context, processes roll, returns result
4. Frontend displays result to user

### Distributed Tracing

- **Trace Propagation**: Frontend → Dice Roller via W3C trace context headers
- **Trace Structure**:
  - Root span: Frontend user interaction
  - Child span: Frontend HTTP client request
  - Child span: Dice Roller HTTP server request
- **Correlation**: Both services include trace_id/span_id in logs for unified trace-to-logs view

### Observability Data Generated

- **Metrics**: HTTP metrics from both services, dice roll counters
- **Logs**: Request/response logs from both services with trace correlation
- **Traces**: Multi-span distributed traces showing Frontend → Dice Roller call chain
- **Dashboards**: Visualize request rates, latencies, and error rates across both services
