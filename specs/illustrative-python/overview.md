## Objectives

We want to create a progressively complicated family of services implemented in Python to demonstrate:

1. How to instrument Python code using OpenTelemetry.
2. How to collect that OpenTelemetry data and route it to an observability stack.
3. How to analyze that OpenTelemetry data once it is in the observability stack.

While we will add complexity in stages, the goal is for each stage to be simple enough to understand but nontrivial enough to demonstrate the use cases of instrumentation and observability.

## Stages

We will pursue this objective through stages. At the end of every stage, we will:

1. Have a functional system of one or more applications, launched as a docker compose project, with instrumented to generate metrics, logs, and traces using OpenTelemetry.
2. Have a useful and meaningful set of dashboards and means of querying our observability data in Grafana.
3. Have a means of create synthetic traffic to generate data for our observability stack.

### Stage 1: Single FastAPI Service (Die rolling service)

#### Application specifications

In this initial stage, we will establish the foundation to which we will add in later stages.

The API should have one functional endpoint: `/roll`. This endpoint takes a required string parameter (`die`) that must be one of "fair" or "risky".

This endpoint simulates the rolling of a 6-sided die. It returns roll as a JSON object, e.g., `{"roll": 5}`. When  `die` is "fair", the service simulates a fair die. When `die` is "risky", the simulates a die that always adds 1 to each roll and has a 10% chance each roll to error out, producing a 500 response. The service will add a random amount of wait time, up to 1 second, before responding.

#### Instrumentation

**Metrics:**
- Use `prometheus-fastapi-instrumentator` for automatic HTTP metrics (request count, duration, status codes)
- Add custom Prometheus metrics:
  - Counter: `dice_rolls_total` with labels `die_type` (fair/risky) and `result` (success/error)
  - Histogram: `dice_roll_value` with label `die_type` to track distribution of roll results
- Expose metrics at `/metrics` endpoint

**Logs:**
- Structured JSON logging to stdout with fields:
  - `timestamp`: ISO 8601 format
  - `level`: INFO, WARNING, ERROR
  - `message`: Human-readable message
  - `trace_id`: OpenTelemetry trace ID (32-char hex)
  - `span_id`: OpenTelemetry span ID (16-char hex)
  - `die_type`: "fair" or "risky" (for roll events)
  - `roll_value`: The actual roll result (for roll events)
- Log events:
  - INFO: Application startup
  - INFO: Each roll request received
  - INFO: Each roll result
  - ERROR: When risky die triggers error condition
  - WARNING: Invalid die type parameter

**Traces:**
- Use OpenTelemetry automatic instrumentation for FastAPI (`opentelemetry-instrumentation-fastapi`)
- Export traces via OTLP HTTP to OpenTelemetry Collector at `http://otel-collector:4318`
- Environment variables:
  - `OTEL_SERVICE_NAME=dice-roller`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
  - `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://otel-collector:4318/v1/traces`
  - `OTEL_TRACES_EXPORTER=otlp`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
- Automatic span creation for HTTP requests
- Add custom span attributes:
  - `die.type`: "fair" or "risky"
  - `die.result`: The roll value
  - `die.error`: true/false (whether risky die triggered error)

#### Traffic generation

To generate traffic, use a Python script that can specify:

1. NUM_USERS: Number of users to simulate
1. MAX_ROLLS_PER_USER: Maximum number of rolls to simulate per user

The script will asynchronously simulate NUM_USERS users, labeled User 1, User 2, etc.. For each user, it will pick a random integer between 1 and MAX_ROLLS_PER_USER to represent the number of rolls that user will make. For each roll, the user picks with equal probability whether to use the `/fair` or `/risky` endpoint. After a user receives the result of its last roll, the script will log that the user has finished its last roll. Once the last user finishes, the script logs that the traffic generation process is complete.

#### Grafana dashboards

Create a dashboard named "Dice Roller - Stage 1" with the following panels:

**Row 1: Overview Metrics (Prometheus)**
- Panel 1: "Request Rate" - Graph showing requests per second
  - Query: `rate(http_requests_total{job="dice-roller"}[1m])`
- Panel 2: "Success Rate" - Gauge showing % of successful requests (status < 500)
  - Query: `sum(rate(http_requests_total{job="dice-roller",status!~"5.."}[5m])) / sum(rate(http_requests_total{job="dice-roller"}[5m])) * 100`
- Panel 3: "Error Rate" - Graph showing errors per second by die type
  - Query: `sum by (die_type) (rate(dice_rolls_total{result="error"}[1m]))`

**Row 2: Latency Metrics (Prometheus)**
- Panel 4: "Request Duration" - Graph with P50, P95, P99 latency
  - Query: `histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="dice-roller"}[5m]))`
  - Add additional queries for P95 (0.95) and P99 (0.99)
- Panel 5: "Average Response Time by Die Type" - Bar chart
  - Query: `avg by (die_type) (rate(http_request_duration_seconds_sum{job="dice-roller"}[5m]) / rate(http_request_duration_seconds_count{job="dice-roller"}[5m]))`

**Row 3: Roll Distribution (Prometheus)**
- Panel 6: "Rolls by Die Type" - Pie chart
  - Query: `sum by (die_type) (dice_rolls_total)`
- Panel 7: "Roll Value Distribution (Fair)" - Histogram
  - Query: `sum by (le) (rate(dice_roll_value_bucket{die_type="fair"}[5m]))`
- Panel 8: "Roll Value Distribution (Risky)" - Histogram
  - Query: `sum by (le) (rate(dice_roll_value_bucket{die_type="risky"}[5m]))`

**Row 4: Logs and Traces**
- Panel 9: "Recent Logs" - Logs panel (Loki)
  - Query: `{container_name="dice-roller"} | json`
- Panel 10: "Error Logs" - Logs panel (Loki)
  - Query: `{container_name="dice-roller"} | json | level="ERROR"`
- Panel 11: "Trace Count" - Stat showing total traces (Tempo)
  - Use Tempo datasource with service name filter `service.name="dice-roller"`

**Row 5: Trace-to-Logs Correlation**
- Panel 12: Instructions panel (Text)
  - Text: "Use Explore → Tempo to search traces, then click 'Logs for this span' to view correlated logs"

### Stage 2: Add a Streamlit frontend

In this stage, we add a Streamlit frontend that can be used to to interact with the backend. The frontend provides a drop down (Risky or Fair) and a Run button on one row, and an output literal textbox on a separate row. When the user presses the Run button, the frontend sends the corresponding request to the backend and populates the output literal textbox with the response status code and body.

#### Instrumentation

**Metrics:**
- Use `prometheus-client` for Python to expose custom metrics at `/metrics`
- Custom Prometheus metrics:
  - Counter: `streamlit_button_clicks_total` with label `die_type`
  - Counter: `streamlit_requests_total` with labels `die_type` and `status_code`
  - Histogram: `streamlit_request_duration_seconds` with label `die_type`
- Expose metrics endpoint that Prometheus can scrape

**Logs:**
- Structured JSON logging to stdout with fields:
  - `timestamp`: ISO 8601 format
  - `level`: INFO, WARNING, ERROR
  - `message`: Human-readable message
  - `trace_id`: OpenTelemetry trace ID (propagated from outgoing request)
  - `span_id`: OpenTelemetry span ID
  - `die_type`: "fair" or "risky" (for button click events)
  - `backend_status`: HTTP status code from backend response
- Log events:
  - INFO: Application startup
  - INFO: Button clicked with die type
  - INFO: Backend response received with status and body summary
  - ERROR: Backend request failed

**Traces:**
- Use OpenTelemetry manual instrumentation with `requests` library
- Export traces via OTLP HTTP to OpenTelemetry Collector
- Environment variables (same as Stage 1):
  - `OTEL_SERVICE_NAME=streamlit-frontend`
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
  - `OTEL_TRACES_EXPORTER=otlp`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`
- Create span for each button click → backend request
- Propagate trace context to backend via HTTP headers (W3C Trace Context)
- Add custom span attributes:
  - `die.type`: "fair" or "risky"
  - `backend.status_code`: HTTP status from backend
  - `backend.url`: Full URL of backend request

#### Traffic generation

**Option 1: Selenium-based UI automation (recommended for realism)**
- Use Selenium WebDriver to control browser
- Script navigates to Streamlit app
- Randomly selects die type from dropdown
- Clicks Run button
- Waits for response to appear
- Simulates realistic user think time (2-5 seconds between actions)

**Option 2: Direct API simulation (simpler, faster)**
- Script makes HTTP requests directly to dice-roller backend
- Emulates what the frontend would do
- Includes trace context headers as if from frontend
- Faster and easier to implement but doesn't test the frontend UI

**Recommended: Use Option 2** - Script parameters:
- `NUM_USERS`: Number of concurrent users
- `MAX_REQUESTS_PER_USER`: Maximum requests per user
- Each user randomly picks die type for each request
- Script logs when each user completes and when all finish
- Generate traces with `streamlit-frontend` as the service name to simulate frontend

#### Grafana dashboards

Update the dashboard to "Dice Roller - Stage 2 (with Frontend)" with new panels:

**Add Row 1.5: Frontend Metrics (Prometheus)**
- Panel: "Frontend Request Rate" - Graph
  - Query: `rate(streamlit_requests_total[1m])`
- Panel: "Frontend Success Rate" - Gauge
  - Query: `sum(rate(streamlit_requests_total{status_code!~"5.."}[5m])) / sum(rate(streamlit_requests_total[5m])) * 100`
- Panel: "Button Clicks by Die Type" - Bar chart
  - Query: `sum by (die_type) (streamlit_button_clicks_total)`

**Add Row 2.5: End-to-End Latency (Prometheus)**
- Panel: "Frontend → Backend Latency" - Graph with P50, P95, P99
  - Query: `histogram_quantile(0.50, rate(streamlit_request_duration_seconds_bucket[5m]))`

**Update Row 4: Logs and Traces**
- Add Panel: "Frontend Logs" - Logs panel (Loki)
  - Query: `{container_name="streamlit-frontend"} | json`
- Update Panel 11: "Distributed Traces" - Instructions (Text)
  - Text: "Use Explore → Tempo, filter by service.name='streamlit-frontend' to see full distributed traces from frontend through backend"

**Add Row 6: Service Dependency**
- Panel: "Service Graph" - Instructions (Text)
  - Text: "Navigate to Explore → Tempo → Service Graph to visualize the dependency between streamlit-frontend and dice-roller"

### Stage 3: Add another FastAPI Service (Die service)

In this stage, we add another FastAPI frontend that will provide specifications for 6 sided die. These specifications include the face values and an error rate. For ease of development, these specifications are stored in a JSON file and loaded into the service at launch. For example, the following specification file describes the fair and risky die:

```
{
    "fair": {
        "faces": [1,2,3,4,5,6],
        "error_rate": 0
    },
    "risky": {
        "faces": [2,3,4,5,6,7],
        "error_rate": 0.1
    }
}
```

This service should provide a single endpoint (`/dice`) that takes an optional string parameter `identifier`. When no `identifier` is specified, the service returns a list containing all valid identifiers, e.g., `{"identifiers": ["fair", "risky"]}`. When specified, the service returns the corresponding specification. Specifying an unknown identifier returns an error code.

Our Frontend changes by using the Die service to populate the dropdown.

Our Roll service changes by looking up the die specification from the Die service.

#### Instrumentation

**Die Service:**

*Metrics:*
- Use `prometheus-fastapi-instrumentator` for automatic HTTP metrics
- Custom Prometheus metrics:
  - Counter: `die_specifications_requested_total` with label `identifier`
  - Counter: `die_list_requests_total`
  - Gauge: `die_specifications_loaded` (number of die specs in memory)
- Expose metrics at `/metrics`

*Logs:*
- Structured JSON logging with trace context (same format as Stage 1)
- Log events:
  - INFO: Service startup, number of die specs loaded
  - INFO: List of all dice requested
  - INFO: Specific die specification requested
  - WARNING: Unknown die identifier requested
  
*Traces:*
- OpenTelemetry automatic instrumentation (same as Stage 1)
- Environment variables: `OTEL_SERVICE_NAME=die-service`
- Custom span attributes:
  - `die.identifier`: The die identifier requested
  - `die.found`: true/false (whether identifier exists)

**Dice Roller Service (Modified):**

*Metrics:*
- Add new counter: `die_service_requests_total` with labels `identifier` and `status`
- Add histogram: `die_service_request_duration_seconds`

*Logs:*
- Add log events:
  - INFO: Querying die service for specification
  - WARNING: Die service returned error or unknown die
  
*Traces:*
- Automatic span creation for outgoing HTTP request to die-service
- Propagate trace context to die-service
- Full distributed trace: frontend → dice-roller → die-service

**Streamlit Frontend (Modified):**

*Application changes:*
- On startup, query die-service `/dice` to get list of identifiers
- Populate dropdown dynamically instead of hardcoded ["fair", "risky"]

*Logs:*
- Add log event:
  - INFO: Die list fetched from die-service (log the identifiers)
  - ERROR: Failed to fetch die list from die-service

*Traces:*
- Create span for die list fetch on app startup

#### Traffic generation

Extend the Stage 2 traffic generation script:
- Script now makes 3-service requests: frontend → dice-roller → die-service
- Before starting user simulation, verify die-service is accessible
- Same parameters: `NUM_USERS`, `MAX_REQUESTS_PER_USER`
- Each user request triggers a chain: frontend calls dice-roller, which calls die-service
- Script logs should show full trace IDs for debugging distributed traces

Alternative: Add a separate script to directly test die-service:
- Query `/dice` repeatedly
- Query `/dice?identifier=fair` and `/dice?identifier=risky`
- Query with invalid identifiers to generate warnings
- Parameters: `NUM_REQUESTS`, `RATE_LIMIT` (requests per second)

#### Grafana dashboards

Create/update dashboard "Dice Roller - Stage 3 (Three Services)" with:

**Add Row: Die Service Metrics (Prometheus)**
- Panel: "Die Service Request Rate" - Graph
  - Query: `rate(http_requests_total{job="die-service"}[1m])`
- Panel: "Die Specifications Requested" - Bar chart
  - Query: `sum by (identifier) (die_specifications_requested_total)`
- Panel: "Die Service Latency" - Graph (P50, P95, P99)
  - Query: `histogram_quantile(0.50, rate(http_request_duration_seconds_bucket{job="die-service"}[5m]))`

**Add Row: Service-to-Service Communication**
- Panel: "Dice Roller → Die Service Request Rate" - Graph
  - Query: `rate(die_service_requests_total[1m])`
- Panel: "Dice Roller → Die Service Errors" - Graph
  - Query: `rate(die_service_requests_total{status=~"5.."}[1m])`
- Panel: "Service-to-Service Latency" - Graph
  - Query: `histogram_quantile(0.95, rate(die_service_request_duration_seconds_bucket[5m]))`

**Update Row: Logs**
- Add Panel: "Die Service Logs" - Logs panel (Loki)
  - Query: `{container_name="die-service"} | json`

**Update Row: Distributed Traces**
- Update instructions panel:
  - Text: "Use Explore → Tempo, search by service.name='streamlit-frontend' to see full distributed traces across all 3 services (frontend → dice-roller → die-service). Click on a trace to see the waterfall view showing timing of each service call."

**Add Row: Service Map**
- Panel: "Service Architecture" - Text/Instructions
  - Text: "Service flow: Streamlit Frontend → Dice Roller → Die Service. View this in Tempo Service Graph."
  - Include diagram or link to Tempo service graph

### Stage 4: Async Rolling

In this stage, we add a `/roll-async` endpoint to the rolling service. This endpoint works similar to the `/roll` endpoint, but takes an additional parameter, `times`, indicating the number of die to roll. The rolling service will make these rolls asynchronously, then return the total of the rolls.

#### Instrumentation

**Dice Roller Service (Modified):**

*Application changes:*
- Add new endpoint: `GET /roll-async?die={die_type}&times={count}`
- Implementation:
  - Query die-service for specification
  - Use `asyncio.gather()` to make `times` concurrent roll operations
  - Each roll is an async function that simulates rolling the die
  - Return: `{"total": sum, "rolls": [r1, r2, ...], "count": times}`
- Each individual async roll should still have random delay and error probability

*Metrics:*
- Add counter: `async_rolls_total` with labels `die_type` and `result`
- Add histogram: `async_roll_batch_size` (tracks the `times` parameter)
- Add histogram: `async_roll_duration_seconds` (time to complete all rolls)
- Add gauge: `async_rolls_in_progress` (active concurrent roll operations)

*Logs:*
- Add log events:
  - INFO: Async roll batch started (log die_type and times)
  - INFO: Each individual async roll within the batch
  - INFO: Async roll batch completed (log total, individual rolls)
  - ERROR: Async roll batch failed
  
*Traces:*
- Create parent span for the entire `/roll-async` request
- Create child spans for each individual async roll operation
- This creates a trace with 1 parent + N children (where N = `times` parameter)
- Child spans run concurrently (overlapping in time in trace waterfall)
- Custom span attributes:
  - Parent span: `async.batch_size`, `async.total_result`
  - Child spans: `async.roll_index`, `die.result`

**Streamlit Frontend (Modified):**

*Application changes:*
- Add number input widget for "Number of rolls" (1-10)
- Add checkbox: "Use async rolling"
- When checked, call `/roll-async` instead of `/roll`
- Display: "Rolled {times} dice, total: {total}, rolls: {rolls}"

*Metrics:*
- Add counter: `async_roll_requests_total` with label `batch_size`

*Logs:*
- Add log event: INFO for async roll requests with batch size

#### Traffic generation

Extend the traffic generation script:
- Add parameter: `ASYNC_PROBABILITY` (0.0-1.0) - probability user chooses async rolling
- Add parameter: `MAX_ASYNC_ROLLS` (default: 10) - max value for `times` parameter
- When user makes an async roll:
  - Pick random `times` value between 1 and `MAX_ASYNC_ROLLS`
  - Call `/roll-async?die={type}&times={times}`
- Log async requests differently: "User X making async roll: {times} dice"
- Script should handle longer response times for async requests

**Performance testing script:**
- Create separate script: `test-async-performance.py`
- Compare performance: 10 sequential `/roll` calls vs. 1 `/roll-async?times=10` call
- Measure and log:
  - Total time for sequential rolls
  - Total time for single async batch
  - Speedup factor
- Output: "Async rolling is {X}x faster than sequential"

#### Grafana dashboards

Update dashboard "Dice Roller - Stage 4 (with Async)" with:

**Add Row: Async Roll Metrics (Prometheus)**
- Panel: "Async vs Sync Roll Rate" - Graph with two lines
  - Query 1: `rate(dice_rolls_total[1m])` (label: "Sync")
  - Query 2: `rate(async_rolls_total[1m]) * 10` (label: "Async batched", assumes avg 10/batch)
- Panel: "Async Batch Size Distribution" - Histogram
  - Query: `histogram_quantile(0.50, rate(async_roll_batch_size_bucket[5m]))` (add P95, P99)
- Panel: "Async Rolls In Progress" - Graph
  - Query: `async_rolls_in_progress`

**Add Row: Async Performance Comparison**
- Panel: "Sync Roll Duration" - Stat showing average
  - Query: `avg(rate(http_request_duration_seconds_sum{handler="/roll"}[5m]) / rate(http_request_duration_seconds_count{handler="/roll"}[5m]))`
- Panel: "Async Roll Duration" - Stat showing average
  - Query: `avg(rate(async_roll_duration_seconds_sum[5m]) / rate(async_roll_duration_seconds_count[5m]))`
- Panel: "Performance Improvement" - Stat
  - Query: Calculated metric showing sync duration / async duration

**Update Row: Distributed Traces**
- Update instructions panel:
  - Text: "Use Explore → Tempo to find async roll traces. Look for traces with multiple concurrent child spans showing parallel execution. The trace waterfall will show overlapping spans for concurrent rolls."

**Add Row: Async Trace Visualization**
- Panel: "Concurrency Example" - Text/Instructions
  - Text: "Search Tempo for traces with service.name='dice-roller' and span.name contains 'async'. The trace view will show a parent span with multiple child spans executing in parallel (overlapping time ranges)."

### Stage 5: Die database

In this stage, we add a database backend for the Die service. The database is seeded with the JSON file specifying all the die, and instead of the Die service storing and looking up information in-memory, it queries the database.

#### Instrumentation

**PostgreSQL Database:**
- Add PostgreSQL container to docker-compose
- Create schema:
  ```sql
  CREATE TABLE die_specifications (
    identifier VARCHAR(50) PRIMARY KEY,
    faces INTEGER[],
    error_rate FLOAT
  );
  ```
- Seed database using init script that reads the JSON file
- Data persisted in Docker volume

**Die Service (Modified):**

*Application changes:*
- Add database connection using `asyncpg` or `psycopg2`
- Replace in-memory dictionary with database queries:
  - `GET /dice` → `SELECT identifier FROM die_specifications`
  - `GET /dice?identifier=X` → `SELECT * FROM die_specifications WHERE identifier = $1`
- Add database connection pool for performance
- Add retry logic for database connection failures

*Metrics:*
- Add counter: `database_queries_total` with labels `query_type` (list/get) and `result` (success/error)
- Add histogram: `database_query_duration_seconds` with label `query_type`
- Add gauge: `database_connection_pool_size`
- Add gauge: `database_connection_pool_available`

*Logs:*
- Add log events:
  - INFO: Database connection established
  - INFO: Database seeded with N die specifications
  - INFO: Database query executed (log query type and identifier if applicable)
  - ERROR: Database connection failed
  - ERROR: Database query failed
  - WARNING: Database connection pool exhausted
  
*Traces:*
- Use OpenTelemetry database instrumentation (`opentelemetry-instrumentation-psycopg2` or `opentelemetry-instrumentation-asyncpg`)
- Automatic span creation for each database query
- Database spans appear as children of the HTTP request span
- Span attributes automatically include:
  - `db.system`: "postgresql"
  - `db.name`: database name
  - `db.statement`: SQL query (sanitized)
  - `db.user`: database user
- Full distributed trace now: frontend → dice-roller → die-service → postgres

**PostgreSQL Exporter (Optional but recommended):**
- Add `postgres_exporter` container to monitor database metrics
- Exposes Prometheus metrics:
  - Connection count
  - Query performance
  - Table sizes
  - Lock statistics
- Prometheus scrapes postgres_exporter

#### Traffic generation

No changes to traffic generation script needed - it should work transparently with the database backend.

**Optional: Database load testing script:**
- Create `test-database-load.py`
- Directly query die-service endpoints at high rate
- Parameters:
  - `QUERIES_PER_SECOND`: Target query rate
  - `DURATION_SECONDS`: How long to run
  - `LIST_TO_GET_RATIO`: Ratio of list queries vs. get queries (e.g., 1:10)
- Measure and log:
  - Achieved QPS
  - Query latency percentiles
  - Error rate
- Output: Database performance metrics under load

**Database failure testing:**
- Script to test resilience:
  - Start traffic generation
  - Stop PostgreSQL container: `docker compose stop postgres`
  - Observe errors in logs and metrics
  - Restart PostgreSQL: `docker compose start postgres`
  - Verify service recovers
  - Check trace data shows database errors during outage

#### Grafana dashboards

Update dashboard "Dice Roller - Stage 5 (with Database)" with:

**Add Row: Database Metrics (Prometheus via postgres_exporter)**
- Panel: "Database Connections" - Graph
  - Query: `pg_stat_database_numbackends{datname="dicedb"}`
- Panel: "Active Queries" - Graph
  - Query: `pg_stat_activity_count{state="active"}`
- Panel: "Database Size" - Stat
  - Query: `pg_database_size_bytes{datname="dicedb"}`

**Add Row: Die Service Database Operations (Prometheus)**
- Panel: "Database Query Rate" - Graph by query type
  - Query: `sum by (query_type) (rate(database_queries_total[1m]))`
- Panel: "Database Query Duration" - Graph with P50, P95, P99
  - Query: `histogram_quantile(0.50, rate(database_query_duration_seconds_bucket[5m]))`
  - Add P95 and P99
- Panel: "Database Errors" - Graph
  - Query: `rate(database_queries_total{result="error"}[1m])`
- Panel: "Connection Pool Status" - Graph with two lines
  - Query 1: `database_connection_pool_size` (label: "Total")
  - Query 2: `database_connection_pool_available` (label: "Available")

**Update Row: Distributed Traces**
- Update instructions panel:
  - Text: "Use Explore → Tempo to see full distributed traces including database queries. Filter by service.name='die-service' and look for child spans with db.system='postgresql'. The trace waterfall shows the database query as part of the overall request flow."

**Add Row: Database Query Examples**
- Panel: "Database Query Logs" - Logs panel (Loki)
  - Query: `{container_name="die-service"} | json | message =~ ".*[Dd]atabase.*"`
- Panel: "Database Span Example" - Text/Instructions
  - Text: "In Tempo traces, database spans show the SQL query, duration, and connection details. Look for spans with 'db.statement' attribute."

**Add Row: Database Health**
- Panel: "Database Status" - Stat
  - Query: `up{job="postgres-exporter"}` (1 = up, 0 = down)
- Panel: "Query Success Rate" - Gauge
  - Query: `sum(rate(database_queries_total{result="success"}[5m])) / sum(rate(database_queries_total[5m])) * 100`

### Stage 6: Usage Tracking

In this stage, we add some usage tracking. This stage has nothing to do with observability but demonstrates how you can route specific log messages to a different location.

To achieve this, we will need to have add some instrumentation to the frontend where we include the field `"usage": true` in log events specifically designed for usage tracking. 

We'll add a dead simple sign-in flow to the streamlit app. We will include `"usage": true` to log events corresponding to:

1. Sign-in
2. Run

