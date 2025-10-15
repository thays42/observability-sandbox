# Trace-to-Logs Correlation Demo

This guide demonstrates the powerful trace-to-logs correlation feature in Stage 3.

## What is Trace-to-Logs Correlation?

Every log entry includes the `trace_id` and `span_id` from the active OpenTelemetry span. This allows you to:
1. Find a trace in Tempo
2. Click on any span
3. Jump directly to the logs for that specific span
4. See exactly what the service was doing during that request

## Step-by-Step Demo

### 1. Generate a Request

```bash
# Make a request and capture the trace ID
RESPONSE=$(curl -s "http://localhost:8105/roll?die=fair")
echo "$RESPONSE" | jq
TRACE_ID=$(echo "$RESPONSE" | jq -r '.trace_id')
echo "Trace ID: $TRACE_ID"
```

Example output:
```json
{
  "roll": 4,
  "trace_id": "615ea7404140f07bf433a34bd7f92705"
}
Trace ID: 615ea7404140f07bf433a34bd7f92705
```

### 2. View the Trace in Grafana

1. Open Grafana: http://localhost:3000
2. Click **Explore** (compass icon in left sidebar)
3. Select **Tempo** from the datasource dropdown
4. In the **Search** tab:
   - Query Type: **Search**
   - Service Name: **frontend**
   - Click **Run query**
5. Find your trace in the results (you can search by trace ID)
6. Click on the trace to open the waterfall view

### 3. Examine the Trace Waterfall

You should see spans from all 3 services:

```
frontend: GET /roll
├─ dice-roller: GET /roll (HTTP client)
   ├─ dice-roller: GET /roll (HTTP server)
      ├─ die-service: GET /dice (HTTP client)
         └─ die-service: GET /dice (HTTP server)
```

### 4. Jump to Logs from a Trace

1. Click on any span (e.g., the "dice-roller: GET /roll" span)
2. In the span details panel, click the **"Logs for this span"** button
3. Grafana automatically switches to Loki datasource
4. Logs are filtered by the trace_id
5. You see all log entries for that specific request!

## What You'll See in the Logs

The logs will show the complete story of that request:

**Frontend logs:**
```json
{
  "timestamp": "2025-10-13T03:20:33Z",
  "level": "INFO",
  "message": "Frontend roll request received",
  "trace_id": "303f39bebdd74f45bc96dbb3dce8f5a6",
  "span_id": "3c6ed5513c5ce23d",
  "die_type": "fair"
}
```

**Dice Roller logs:**
```json
{
  "timestamp": "2025-10-13T03:20:33Z",
  "level": "INFO",
  "message": "Querying die service for specification",
  "trace_id": "303f39bebdd74f45bc96dbb3dce8f5a6",
  "span_id": "1788ca29c51d2731",
  "identifier": "fair"
}
```

**Die Service logs:**
```json
{
  "timestamp": "2025-10-13T03:20:33Z",
  "level": "INFO",
  "message": "Die specification requested",
  "trace_id": "303f39bebdd74f45bc96dbb3dce8f5a6",
  "span_id": "f8303be7f55d8be3",
  "identifier": "fair"
}
```

All with the **same trace_id**! 🎉

## Manual Log Query by Trace ID

You can also query logs directly by trace ID:

### In Grafana Explore (Loki)

```logql
{container_name=~".*-stage3"} | json | trace_id="615ea7404140f07bf433a34bd7f92705"
```

### Via cURL

```bash
TRACE_ID="615ea7404140f07bf433a34bd7f92705"
curl -s "http://localhost:3100/loki/api/v1/query_range" \
  --get \
  --data-urlencode "query={container_name=~\".*-stage3\"} | json | trace_id=\"$TRACE_ID\"" \
  | jq '.data.result[].values[][1]' -r | jq
```

## Advanced Queries

### Find all logs for requests that touched a specific service

```logql
{container_name="dice-roller-stage3"} 
| json 
| message =~ "Querying die service"
```

### Find all error logs with their traces

```logql
{container_name=~".*-stage3"} 
| json 
| level="ERROR"
| line_format "{{.trace_id}} - {{.message}}"
```

### Find slow requests (if you add duration to logs)

```logql
{container_name="frontend-stage3"} 
| json 
| duration > 0.5
```

## Why This Matters

### Without Trace-to-Logs Correlation:

1. User reports: "My request failed"
2. You search through logs for errors: hundreds of results
3. Which error belongs to which request? 🤷
4. You spend hours correlating timestamps across services

### With Trace-to-Logs Correlation:

1. User reports: "My request failed"
2. Find the trace in Tempo (by time, service, user, etc.)
3. Click "Logs for this span"
4. See **exactly** what happened in **all services**
5. Problem identified in minutes! ✨

## Real-World Debugging Example

### Scenario: Frontend reports 500 error

1. **Find the trace:**
   ```
   Grafana → Tempo → Search
   Service: frontend
   Status: error
   ```

2. **Examine the waterfall:**
   - See which service returned the error
   - See how long each hop took
   - Identify the bottleneck

3. **Jump to logs:**
   - Click on the red (error) span
   - Click "Logs for this span"
   - See the exact error message
   - See what led up to the error

4. **Correlate across services:**
   - Same trace_id in all services
   - See the full request flow
   - Understand cause and effect

## Testing Error Scenarios

### Generate an error with the risky die:

```bash
# Risky die has 10% error rate
for i in {1..20}; do
  RESPONSE=$(curl -s "http://localhost:8105/roll?die=risky")
  STATUS=$?
  if [ $STATUS -ne 0 ]; then
    echo "Request failed!"
  else
    TRACE_ID=$(echo "$RESPONSE" | jq -r '.trace_id // "no-trace"')
    ROLL=$(echo "$RESPONSE" | jq -r '.roll // "ERROR"')
    echo "Roll: $ROLL, Trace: $TRACE_ID"
    
    if [ "$ROLL" == "ERROR" ]; then
      echo "Found error! Trace ID: $TRACE_ID"
      echo "View in Grafana: http://localhost:3000/explore?schemaVersion=1&panes=%7B%22tempo%22:%7B%22datasource%22:%22tempo%22,%22queries%22:%5B%7B%22query%22:%22$TRACE_ID%22%7D%5D%7D%7D"
    fi
  fi
  sleep 0.5
done
```

## Best Practices

### 1. Always Include Trace Context in Logs

✅ **Good:**
```python
logger.info(
    "Processing request",
    extra={
        "extra_fields": {
            "user_id": user_id,
            "request_type": "roll",
        }
    }
)
# trace_id and span_id automatically added by JSONFormatter
```

❌ **Bad:**
```python
print(f"Processing request for {user_id}")  # No trace context!
```

### 2. Use Structured Logging

✅ **Good:**
```python
logger.info(
    "Die service request completed",
    extra={"extra_fields": {"identifier": "fair", "duration": 0.05}}
)
```

❌ **Bad:**
```python
logger.info(f"Die service request for fair took 0.05s")  # Hard to parse!
```

### 3. Log at Service Boundaries

Always log when:
- Receiving a request
- Calling another service
- Receiving a response from another service
- Completing a request

This creates a clear audit trail in the traces!

## Summary

Trace-to-logs correlation is one of the most powerful features of modern observability:

- **Traces** show you the "what" and "when" (request flow, timing)
- **Logs** show you the "why" and "how" (detailed context, errors)
- **Together** they give you complete visibility into your distributed system

Stage 3 demonstrates this perfectly with 3 services creating multi-hop traces that seamlessly connect to detailed logs across all services! 🎯
