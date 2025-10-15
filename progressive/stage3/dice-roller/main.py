import logging
import json
import random
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
import requests

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
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)

# Create FastAPI app
app = FastAPI(title="Dice Roller API", version="2.0.0")

# Instrument FastAPI for automatic tracing, excluding /metrics endpoint
FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")

# Instrument requests library for automatic trace propagation
RequestsInstrumentor().instrument()

# Instrument with Prometheus
Instrumentator().instrument(app).expose(app)

# Custom Prometheus metrics
dice_rolls_total = Counter(
    "dice_rolls_total", "Total number of dice rolls", ["die_type", "result"]
)

dice_roll_value = Histogram(
    "dice_roll_value",
    "Distribution of roll values",
    ["die_type"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8],
)

die_service_requests_total = Counter(
    "die_service_requests_total",
    "Total requests to die service",
    ["identifier", "status"],
)

die_service_request_duration_seconds = Histogram(
    "die_service_request_duration_seconds",
    "Die service request duration in seconds",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Die service URL
DIE_SERVICE_URL = "http://die-service-stage3:8000"


def get_die_specification(identifier: str):
    """Fetch die specification from die service."""
    span = trace.get_current_span()
    span.set_attribute("die_service.identifier", identifier)

    logger.info(
        "Querying die service for specification",
        extra={"extra_fields": {"identifier": identifier}},
    )

    # Prepare headers with trace context
    headers = {}
    inject(headers)

    start_time = time.time()

    try:
        response = requests.get(
            f"{DIE_SERVICE_URL}/dice",
            params={"identifier": identifier},
            headers=headers,
            timeout=2.0,
        )

        duration = time.time() - start_time
        die_service_request_duration_seconds.observe(duration)

        if response.status_code == 200:
            die_service_requests_total.labels(
                identifier=identifier, status="success"
            ).inc()

            data = response.json()
            spec = data.get("specification", {})

            logger.info(
                "Die specification retrieved from service",
                extra={
                    "extra_fields": {
                        "identifier": identifier,
                        "faces": spec.get("faces"),
                        "error_rate": spec.get("error_rate"),
                        "duration": duration,
                    }
                },
            )

            return spec
        else:
            die_service_requests_total.labels(
                identifier=identifier, status=f"error_{response.status_code}"
            ).inc()

            logger.warning(
                "Die service returned error",
                extra={
                    "extra_fields": {
                        "identifier": identifier,
                        "status_code": response.status_code,
                    }
                },
            )
            return None

    except requests.exceptions.Timeout:
        die_service_requests_total.labels(identifier=identifier, status="timeout").inc()
        logger.error(
            "Die service request timed out",
            extra={"extra_fields": {"identifier": identifier}},
        )
        return None
    except requests.exceptions.ConnectionError:
        die_service_requests_total.labels(
            identifier=identifier, status="connection_error"
        ).inc()
        logger.error(
            "Failed to connect to die service",
            extra={"extra_fields": {"identifier": identifier}},
        )
        return None
    except Exception as e:
        die_service_requests_total.labels(identifier=identifier, status="error").inc()
        logger.error(
            f"Error querying die service: {str(e)}",
            extra={"extra_fields": {"identifier": identifier}},
        )
        return None


@app.on_event("startup")
async def startup_event():
    logger.info("Dice Roller API starting up (Stage 3 - with die service integration)")

    # Verify die service connectivity
    try:
        response = requests.get(f"{DIE_SERVICE_URL}/", timeout=5.0)
        if response.status_code == 200:
            logger.info("Die service connectivity verified")
        else:
            logger.warning(f"Die service returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not connect to die service: {e}")


@app.get("/")
async def root():
    return {
        "service": "Dice Roller API",
        "version": "2.0.0",
        "stage": "3",
        "endpoints": ["/roll"],
        "integration": "die-service",
    }


@app.get("/roll")
async def roll_die(
    die: str = Query(..., description="Type of die to roll"),
):
    """
    Roll a die based on specification from die service.
    The die service provides the faces and error rate for each die type.
    """
    span = trace.get_current_span()
    span.set_attribute("die.type", die)

    # Log the roll request
    logger.info("Roll request received", extra={"extra_fields": {"die_type": die}})

    # Get die specification from die service
    spec = get_die_specification(die)

    if spec is None:
        logger.error(
            "Failed to get die specification",
            extra={"extra_fields": {"die_type": die}},
        )
        dice_rolls_total.labels(die_type=die, result="error").inc()
        raise HTTPException(
            status_code=503,
            detail=f"Die service unavailable or die '{die}' not found",
        )

    # Extract specification details
    faces = spec.get("faces", [1, 2, 3, 4, 5, 6])
    error_rate = spec.get("error_rate", 0.0)

    span.set_attribute("die.faces", str(faces))
    span.set_attribute("die.error_rate", error_rate)

    # Add random delay (up to 1 second)
    delay = random.uniform(0, 1.0)
    time.sleep(delay)

    try:
        # Check if error should be triggered
        if random.random() < error_rate:
            # Error case
            span.set_attribute("die.error", True)
            logger.error(
                "Die triggered error condition",
                extra={
                    "extra_fields": {
                        "die_type": die,
                        "error_rate": error_rate,
                    }
                },
            )
            dice_rolls_total.labels(die_type=die, result="error").inc()
            raise HTTPException(status_code=500, detail=f"Die '{die}' failed!")

        # Success case: roll the die using specified faces
        roll_value = random.choice(faces)
        span.set_attribute("die.result", roll_value)
        span.set_attribute("die.error", False)

        # Log the result
        logger.info(
            "Roll completed",
            extra={
                "extra_fields": {
                    "die_type": die,
                    "roll_value": roll_value,
                    "faces": faces,
                }
            },
        )

        # Update metrics
        dice_rolls_total.labels(die_type=die, result="success").inc()
        dice_roll_value.labels(die_type=die).observe(roll_value)

        return {"roll": roll_value}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error during roll: {str(e)}",
            extra={"extra_fields": {"die_type": die}},
        )
        dice_rolls_total.labels(die_type=die, result="error").inc()
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
