import logging
import json
import random
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter, Histogram
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
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)

# Create FastAPI app
app = FastAPI(title="Dice Roller API", version="1.0.0")


# Instrument FastAPI for automatic tracing, excluding /metrics endpoint
def exclude_metrics_endpoint(scope):
    """Exclude /metrics endpoint from tracing"""
    return scope.get("path") == "/metrics"


FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")

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


@app.on_event("startup")
async def startup_event():
    logger.info("Dice Roller API starting up")


@app.get("/")
async def root():
    return {"service": "Dice Roller API", "version": "1.0.0", "endpoints": ["/roll"]}


@app.get("/roll")
async def roll_die(
    die: Literal["fair", "risky"] = Query(..., description="Type of die to roll"),
):
    """
    Roll a 6-sided die.
    - fair: Standard fair die (1-6)
    - risky: Adds 1 to each roll (2-7) with 10% chance of error
    """
    span = trace.get_current_span()
    span.set_attribute("die.type", die)

    # Log the roll request
    logger.info("Roll request received", extra={"extra_fields": {"die_type": die}})

    # Add random delay (up to 1 second)
    delay = random.uniform(0, 1.0)
    time.sleep(delay)

    try:
        if die == "fair":
            # Fair die: roll 1-6
            roll_value = random.randint(1, 6)
            span.set_attribute("die.result", roll_value)
            span.set_attribute("die.error", False)

            # Log the result
            logger.info(
                "Roll completed",
                extra={"extra_fields": {"die_type": die, "roll_value": roll_value}},
            )

            # Update metrics
            dice_rolls_total.labels(die_type=die, result="success").inc()
            dice_roll_value.labels(die_type=die).observe(roll_value)

            return {"roll": roll_value}

        elif die == "risky":
            # Risky die: 10% chance of error, otherwise roll 2-7
            if random.random() < 0.1:
                # Error case
                span.set_attribute("die.error", True)
                logger.error(
                    "Risky die triggered error condition",
                    extra={"extra_fields": {"die_type": die}},
                )
                dice_rolls_total.labels(die_type=die, result="error").inc()
                raise HTTPException(status_code=500, detail="Risky die failed!")
            else:
                # Success case: roll 1-6 and add 1
                base_roll = random.randint(1, 6)
                roll_value = base_roll + 1
                span.set_attribute("die.result", roll_value)
                span.set_attribute("die.error", False)

                # Log the result
                logger.info(
                    "Roll completed",
                    extra={"extra_fields": {"die_type": die, "roll_value": roll_value}},
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
