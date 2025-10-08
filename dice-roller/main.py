import random
import re
import logging
import json
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace

# Configure JSON logging with trace context
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add trace context if available
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_data["trace_id"] = format(ctx.trace_id, "032x")
            log_data["span_id"] = format(ctx.span_id, "016x")
            log_data["trace_flags"] = ctx.trace_flags

        return json.dumps(log_data)

# Set up logger
logger = logging.getLogger("dice-roller")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)

app = FastAPI()

# Instrument the app with Prometheus metrics
Instrumentator().instrument(app).expose(app)


@app.get("/roll/{dice}")
def roll_dice(dice: str):
    """
    Roll dice in XdY format (e.g., 3d6 rolls 3 six-sided dice).
    Returns JSON with total and individual rolls.
    """
    logger.info(f"Rolling dice: {dice}")

    # Parse the dice notation
    match = re.match(r"^(\d+)d(\d+)$", dice.lower())
    if not match:
        logger.warning(f"Invalid dice format received: {dice}")
        raise HTTPException(
            status_code=400,
            detail="Invalid dice format. Use XdY where X and Y are positive integers (e.g., 3d6)"
        )

    num_dice = int(match.group(1))
    num_sides = int(match.group(2))

    # Validate positive integers
    if num_dice <= 0 or num_sides <= 0:
        logger.warning(f"Invalid dice values: {num_dice}d{num_sides}")
        raise HTTPException(
            status_code=400,
            detail="Both X and Y must be positive integers greater than 0"
        )

    # Roll the dice
    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    total = sum(rolls)

    logger.info(f"Rolled {num_dice}d{num_sides}: total={total}, rolls={rolls}")

    return {"total": total, "rolls": rolls}


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Dice Roller API - Use /roll/XdY to roll dice (e.g., /roll/2d6)"}