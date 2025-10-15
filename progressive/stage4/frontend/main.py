import logging
import json
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import requests
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import inject


# Custom JSON formatter for structured logging with trace context
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
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
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Initialize OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint="http://alloy:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)

# Create FastAPI app
app = FastAPI(title="Dice Roller Frontend", version="3.0.0")

# Instrument FastAPI for automatic tracing, excluding /metrics
FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")

# Instrument requests library for automatic trace propagation
RequestsInstrumentor().instrument()

# Instrument with Prometheus
Instrumentator().instrument(app).expose(app)

# Custom Prometheus metrics
frontend_requests_total = Counter(
    "frontend_requests_total",
    "Total number of frontend requests",
    ["die_type", "status"],
)

backend_requests_total = Counter(
    "backend_requests_total",
    "Total number of backend requests from frontend",
    ["die_type", "status_code"],
)

backend_request_duration_seconds = Histogram(
    "backend_request_duration_seconds",
    "Backend request duration in seconds",
    ["die_type"],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0],
)

# NEW: Async roll metrics
async_roll_requests_total = Counter(
    "async_roll_requests_total",
    "Total number of async roll requests from frontend",
    ["batch_size"],
)

# Service URLs
DICE_ROLLER_URL = "http://dice-roller-stage4:8000"
DIE_SERVICE_URL = "http://die-service-stage4:8000"

# Cache for available die types
available_die_types = ["fair", "risky"]  # Default fallback


def fetch_available_die_types():
    """Fetch available die types from die service."""
    global available_die_types

    logger.info("Fetching available die types from die service")

    try:
        headers = {}
        inject(headers)  # Propagate trace context

        response = requests.get(f"{DIE_SERVICE_URL}/dice", headers=headers, timeout=3.0)

        if response.status_code == 200:
            data = response.json()
            identifiers = data.get("identifiers", [])

            if identifiers:
                available_die_types = identifiers
                logger.info(
                    "Die list fetched from die service",
                    extra={
                        "extra_fields": {
                            "count": len(identifiers),
                            "identifiers": identifiers,
                        }
                    },
                )
            else:
                logger.warning("Die service returned empty identifier list")
        else:
            logger.error(
                "Failed to fetch die list from die service",
                extra={"extra_fields": {"status_code": response.status_code}},
            )
    except Exception as e:
        logger.error(
            f"Error fetching die list from die service: {str(e)}",
            extra={"extra_fields": {"error": str(e)}},
        )


@app.on_event("startup")
async def startup_event():
    logger.info("Frontend API starting up (Stage 4 - with async rolling support)")

    # Fetch available die types from die service
    fetch_available_die_types()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve a simple HTML UI with async rolling support."""

    # Generate options HTML from available die types
    options_html = ""
    for die_type in available_die_types:
        # Capitalize first letter for display
        display_name = die_type.capitalize()
        options_html += f'<option value="{die_type}">{display_name} Die</option>\n                    '

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dice Roller Frontend - Stage 4</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #333; }}
            .stage-badge {{
                display: inline-block;
                background-color: #9C27B0;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-left: 10px;
            }}
            select, button, input {{
                padding: 10px;
                font-size: 16px;
                margin: 10px 5px;
            }}
            button {{
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }}
            button:hover {{ background-color: #45a049; }}
            #result {{
                margin-top: 20px;
                padding: 15px;
                background-color: #e7f3ff;
                border-radius: 5px;
                display: none;
            }}
            .trace-info {{
                font-size: 12px;
                color: #666;
                margin-top: 10px;
                font-family: monospace;
            }}
            .info {{
                background-color: #f3e5f5;
                padding: 10px;
                border-radius: 5px;
                margin-top: 10px;
                font-size: 14px;
            }}
            .async-controls {{
                background-color: #f0f0f0;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }}
            input[type="number"] {{
                width: 60px;
            }}
            label {{
                margin-right: 10px;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎲 Dice Roller <span class="stage-badge">Stage 4</span></h1>
            <p>Roll dice with optional async/concurrent rolling</p>

            <div class="info">
                <strong>New Feature:</strong> Async rolling lets you roll multiple dice concurrently!<br>
                <strong>Architecture:</strong> Frontend → Dice Roller → Die Service
            </div>

            <div>
                <select id="dieType">
                    {options_html}
                </select>
            </div>

            <div class="async-controls">
                <label>
                    <input type="checkbox" id="useAsync"> Use Async Rolling
                </label>
                <br>
                <label for="numRolls">Number of rolls:</label>
                <input type="number" id="numRolls" min="1" max="20" value="5" disabled>
                <span style="font-size: 12px; color: #666;">(1-20)</span>
            </div>

            <div>
                <button onclick="rollDice()">Roll</button>
            </div>

            <div id="result"></div>
        </div>

        <script>
            // Enable/disable number input based on checkbox
            document.getElementById('useAsync').addEventListener('change', function() {{
                document.getElementById('numRolls').disabled = !this.checked;
            }});

            async function rollDice() {{
                const dieType = document.getElementById('dieType').value;
                const useAsync = document.getElementById('useAsync').checked;
                const numRolls = parseInt(document.getElementById('numRolls').value);
                const resultDiv = document.getElementById('result');

                resultDiv.innerHTML = 'Rolling...';
                resultDiv.style.display = 'block';

                try {{
                    let url, response;

                    if (useAsync) {{
                        // Call async endpoint
                        url = `/roll-async?die=${{dieType}}&times=${{numRolls}}`;
                    }} else {{
                        // Call regular endpoint
                        url = `/roll?die=${{dieType}}`;
                    }}

                    response = await fetch(url);
                    const data = await response.json();

                    if (response.ok) {{
                        if (useAsync) {{
                            resultDiv.innerHTML = `
                                <h2>🎲 Async Roll Results</h2>
                                <p><strong>Total:</strong> ${{data.total}}</p>
                                <p><strong>Rolls:</strong> [${{data.rolls.join(', ')}}]</p>
                                <p><strong>Count:</strong> ${{data.count}} dice</p>
                                <p><strong>Die type:</strong> ${{dieType}}</p>
                                ${{data.trace_id ? `<div class="trace-info">Trace ID: ${{data.trace_id}}</div>` : ''}}
                            `;
                        }} else {{
                            resultDiv.innerHTML = `
                                <h2>Result: ${{data.roll}}</h2>
                                <p>Die type: ${{dieType}}</p>
                                ${{data.trace_id ? `<div class="trace-info">Trace ID: ${{data.trace_id}}</div>` : ''}}
                            `;
                        }}
                        resultDiv.style.backgroundColor = '#e7f3ff';
                    }} else {{
                        resultDiv.innerHTML = `
                            <h2>Error</h2>
                            <p>${{data.detail || 'Unknown error'}}</p>
                        `;
                        resultDiv.style.backgroundColor = '#ffe7e7';
                    }}
                }} catch (error) {{
                    resultDiv.innerHTML = `
                        <h2>Error</h2>
                        <p>Failed to connect to backend: ${{error.message}}</p>
                    `;
                    resultDiv.style.backgroundColor = '#ffe7e7';
                }}
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/roll")
async def roll_die(
    die: str = Query(..., description="Type of die to roll"),
):
    """
    Frontend endpoint that calls the backend dice roller service.
    Propagates trace context to backend for distributed tracing.
    """
    span = trace.get_current_span()
    span.set_attribute("die.type", die)

    # Log the request
    logger.info(
        "Frontend roll request received", extra={"extra_fields": {"die_type": die}}
    )

    # Record frontend request metric
    frontend_requests_total.labels(die_type=die, status="received").inc()

    # Prepare headers with trace context for propagation
    headers = {}
    inject(headers)  # Inject W3C Trace Context headers

    try:
        start_time = time.time()

        # Call backend with trace context
        response = requests.get(
            f"{DICE_ROLLER_URL}/roll", params={"die": die}, headers=headers, timeout=5.0
        )

        duration = time.time() - start_time

        # Record metrics
        backend_requests_total.labels(
            die_type=die, status_code=response.status_code
        ).inc()
        backend_request_duration_seconds.labels(die_type=die).observe(duration)

        # Add backend response details to span
        span.set_attribute("backend.status_code", response.status_code)
        span.set_attribute("backend.url", f"{DICE_ROLLER_URL}/roll")
        span.set_attribute("backend.duration", duration)

        if response.status_code == 200:
            result = response.json()
            roll_value = result.get("roll")

            span.set_attribute("roll.value", roll_value)

            # Log successful response
            logger.info(
                "Backend response received",
                extra={
                    "extra_fields": {
                        "die_type": die,
                        "backend_status": response.status_code,
                        "roll_value": roll_value,
                        "duration": duration,
                    }
                },
            )

            frontend_requests_total.labels(die_type=die, status="success").inc()

            # Add trace ID to response for debugging
            if span.get_span_context().is_valid:
                ctx = span.get_span_context()
                result["trace_id"] = format(ctx.trace_id, "032x")

            return result
        else:
            # Backend returned error
            logger.error(
                "Backend returned error",
                extra={
                    "extra_fields": {
                        "die_type": die,
                        "backend_status": response.status_code,
                    }
                },
            )
            frontend_requests_total.labels(die_type=die, status="error").inc()
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Backend error: {response.text}",
            )

    except requests.exceptions.Timeout:
        logger.error(
            "Backend request timed out", extra={"extra_fields": {"die_type": die}}
        )
        frontend_requests_total.labels(die_type=die, status="timeout").inc()
        raise HTTPException(status_code=504, detail="Backend request timed out")
    except requests.exceptions.ConnectionError as e:
        logger.error(
            "Failed to connect to backend", extra={"extra_fields": {"die_type": die}}
        )
        frontend_requests_total.labels(die_type=die, status="connection_error").inc()
        raise HTTPException(
            status_code=503, detail=f"Could not connect to backend at {DICE_ROLLER_URL}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error: {str(e)}", extra={"extra_fields": {"die_type": die}}
        )
        frontend_requests_total.labels(die_type=die, status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/roll-async")
async def roll_async(
    die: str = Query(..., description="Type of die to roll"),
    times: int = Query(..., description="Number of dice to roll", ge=1, le=20),
):
    """
    Frontend endpoint that calls the backend async dice roller.
    Propagates trace context to backend for distributed tracing.
    """
    span = trace.get_current_span()
    span.set_attribute("die.type", die)
    span.set_attribute("async.batch_size", times)

    # Log the request
    logger.info(
        "Frontend async roll request received",
        extra={"extra_fields": {"die_type": die, "times": times}},
    )

    # Record frontend async request metric
    frontend_requests_total.labels(die_type=die, status="received").inc()
    async_roll_requests_total.labels(batch_size=str(times)).inc()

    # Prepare headers with trace context for propagation
    headers = {}
    inject(headers)

    try:
        start_time = time.time()

        # Call backend async endpoint with trace context
        response = requests.get(
            f"{DICE_ROLLER_URL}/roll-async",
            params={"die": die, "times": times},
            headers=headers,
            timeout=10.0,  # Longer timeout for async operations
        )

        duration = time.time() - start_time

        # Record metrics
        backend_requests_total.labels(
            die_type=die, status_code=response.status_code
        ).inc()
        backend_request_duration_seconds.labels(die_type=die).observe(duration)

        # Add backend response details to span
        span.set_attribute("backend.status_code", response.status_code)
        span.set_attribute("backend.url", f"{DICE_ROLLER_URL}/roll-async")
        span.set_attribute("backend.duration", duration)

        if response.status_code == 200:
            result = response.json()
            total = result.get("total")
            rolls = result.get("rolls", [])

            span.set_attribute("async.total_result", total)

            # Log successful response
            logger.info(
                "Backend async response received",
                extra={
                    "extra_fields": {
                        "die_type": die,
                        "times": times,
                        "backend_status": response.status_code,
                        "total": total,
                        "rolls": rolls,
                        "duration": duration,
                    }
                },
            )

            frontend_requests_total.labels(die_type=die, status="success").inc()

            # Add trace ID to response for debugging
            if span.get_span_context().is_valid:
                ctx = span.get_span_context()
                result["trace_id"] = format(ctx.trace_id, "032x")

            return result
        else:
            # Backend returned error
            logger.error(
                "Backend async returned error",
                extra={
                    "extra_fields": {
                        "die_type": die,
                        "times": times,
                        "backend_status": response.status_code,
                    }
                },
            )
            frontend_requests_total.labels(die_type=die, status="error").inc()
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Backend error: {response.text}",
            )

    except requests.exceptions.Timeout:
        logger.error(
            "Backend async request timed out",
            extra={"extra_fields": {"die_type": die, "times": times}},
        )
        frontend_requests_total.labels(die_type=die, status="timeout").inc()
        raise HTTPException(status_code=504, detail="Backend request timed out")
    except requests.exceptions.ConnectionError as e:
        logger.error(
            "Failed to connect to backend for async roll",
            extra={"extra_fields": {"die_type": die, "times": times}},
        )
        frontend_requests_total.labels(die_type=die, status="connection_error").inc()
        raise HTTPException(
            status_code=503, detail=f"Could not connect to backend at {DICE_ROLLER_URL}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in async roll: {str(e)}",
            extra={"extra_fields": {"die_type": die, "times": times}},
        )
        frontend_requests_total.labels(die_type=die, status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
