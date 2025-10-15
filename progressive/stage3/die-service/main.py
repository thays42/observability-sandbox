import logging
import json
import os
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


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
app = FastAPI(title="Die Service API", version="1.0.0")

# Instrument FastAPI for automatic tracing, excluding /metrics endpoint
FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")

# Instrument with Prometheus
Instrumentator().instrument(app).expose(app)

# Custom Prometheus metrics
die_specifications_requested_total = Counter(
    "die_specifications_requested_total",
    "Total number of die specification requests",
    ["identifier"],
)

die_list_requests_total = Counter(
    "die_list_requests_total",
    "Total number of die list requests",
)

die_specifications_loaded = Gauge(
    "die_specifications_loaded",
    "Number of die specifications loaded in memory",
)

# In-memory storage for die specifications
die_specifications = {}


def load_die_specifications(file_path: str = "die_specifications.json"):
    """Load die specifications from JSON file."""
    global die_specifications

    try:
        with open(file_path, "r") as f:
            die_specifications = json.load(f)

        die_specifications_loaded.set(len(die_specifications))

        logger.info(
            "Die specifications loaded",
            extra={
                "extra_fields": {
                    "count": len(die_specifications),
                    "identifiers": list(die_specifications.keys()),
                }
            },
        )
        return True
    except FileNotFoundError:
        logger.error(f"Die specifications file not found: {file_path}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in die specifications file: {e}")
        return False


@app.on_event("startup")
async def startup_event():
    logger.info("Die Service API starting up")

    # Load die specifications from file
    if not load_die_specifications():
        logger.warning(
            "Failed to load die specifications - service may not work correctly"
        )


@app.get("/")
async def root():
    return {
        "service": "Die Service API",
        "version": "1.0.0",
        "endpoints": ["/dice", "/dice?identifier={id}"],
        "loaded_specifications": len(die_specifications),
    }


@app.get("/dice")
async def get_die_specifications(
    identifier: Optional[str] = Query(None, description="Die identifier to retrieve"),
):
    """
    Get die specifications.
    - No identifier: Returns list of all available die identifiers
    - With identifier: Returns specification for that specific die
    """
    span = trace.get_current_span()

    if identifier is None:
        # Return list of all identifiers
        die_list_requests_total.inc()

        identifiers = list(die_specifications.keys())
        span.set_attribute("request.type", "list")
        span.set_attribute("die.count", len(identifiers))

        logger.info(
            "Die list requested",
            extra={
                "extra_fields": {
                    "count": len(identifiers),
                    "identifiers": identifiers,
                }
            },
        )

        return {"identifiers": identifiers}

    else:
        # Return specific die specification
        span.set_attribute("request.type", "get")
        span.set_attribute("die.identifier", identifier)

        logger.info(
            "Die specification requested",
            extra={"extra_fields": {"identifier": identifier}},
        )

        if identifier in die_specifications:
            die_specifications_requested_total.labels(identifier=identifier).inc()
            span.set_attribute("die.found", True)

            spec = die_specifications[identifier]

            logger.info(
                "Die specification found",
                extra={
                    "extra_fields": {
                        "identifier": identifier,
                        "faces": spec["faces"],
                        "error_rate": spec["error_rate"],
                    }
                },
            )

            return {
                "identifier": identifier,
                "specification": spec,
            }
        else:
            span.set_attribute("die.found", False)

            logger.warning(
                "Unknown die identifier requested",
                extra={
                    "extra_fields": {
                        "identifier": identifier,
                        "available_identifiers": list(die_specifications.keys()),
                    }
                },
            )

            raise HTTPException(
                status_code=404,
                detail=f"Die identifier '{identifier}' not found. Available: {list(die_specifications.keys())}",
            )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
