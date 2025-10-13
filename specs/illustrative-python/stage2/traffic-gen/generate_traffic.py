#!/usr/bin/env python3
"""
Traffic generation script for Stage 2 (Frontend → Backend).

Simulates multiple concurrent users making requests through the frontend to backend,
with proper trace context propagation.
"""

import asyncio
import httpx
import random
import logging
from datetime import datetime

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import inject

# Configuration
NUM_USERS = 10
MAX_ROLLS_PER_USER = 20
BACKEND_URL = "http://localhost:8101"  # Dice roller backend for stage2
OTEL_COLLECTOR_URL = "http://localhost:4318/v1/traces"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize OpenTelemetry tracing to simulate frontend
resource = Resource(attributes={"service.name": "traffic-generator"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_COLLECTOR_URL)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer("traffic-generator")


async def simulate_user(user_id: int, num_rolls: int):
    """Simulate a single user making multiple frontend requests to backend."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for roll_num in range(num_rolls):
            die_type = random.choice(["fair", "risky"])

            # Create a span to simulate frontend request
            with tracer.start_as_current_span(
                "simulated_frontend_request",
                attributes={
                    "user.id": user_id,
                    "die.type": die_type,
                    "roll.number": roll_num + 1,
                },
            ) as span:
                # Inject trace context into headers (W3C Trace Context)
                headers = {}
                inject(headers)

                try:
                    response = await client.get(
                        f"{BACKEND_URL}/roll", params={"die": die_type}, headers=headers
                    )

                    if response.status_code == 200:
                        result = response.json()
                        logging.info(
                            f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                            f"{die_type} -> {result['roll']}"
                        )
                        span.set_attribute("roll.value", result["roll"])
                        span.set_attribute("backend.status", "success")
                    else:
                        logging.warning(
                            f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                            f"{die_type} -> HTTP {response.status_code}"
                        )
                        span.set_attribute("backend.status", "error")
                        span.set_attribute("backend.status_code", response.status_code)

                except httpx.TimeoutException:
                    logging.error(
                        f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                        f"{die_type} -> TIMEOUT"
                    )
                    span.set_attribute("backend.status", "timeout")
                except Exception as e:
                    logging.error(
                        f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                        f"{die_type} -> ERROR: {e}"
                    )
                    span.set_attribute("backend.status", "error")
                    span.set_attribute("error.message", str(e))

            # Random think time between requests (0.5-2 seconds)
            await asyncio.sleep(random.uniform(0.5, 2.0))

    logging.info(f"User {user_id} finished all {num_rolls} rolls")


async def main():
    """Main entry point for traffic generation."""
    start_time = datetime.now()
    logging.info(
        f"Starting traffic generation: {NUM_USERS} users, "
        f"up to {MAX_ROLLS_PER_USER} rolls per user"
    )
    logging.info(f"Simulating frontend → backend traffic with trace propagation")

    # Check if backend is available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(BACKEND_URL)
            if response.status_code != 200:
                logging.error(
                    f"Backend not responding correctly: {response.status_code}"
                )
                return
            logging.info(f"Backend available: {response.json()}")
    except Exception as e:
        logging.error(f"Backend not available at {BACKEND_URL}: {e}")
        logging.info(
            "Make sure Stage 2 is running: cd specs/illustrative-python/stage2 && docker compose up -d"
        )
        return

    # Create user simulation tasks
    tasks = []
    for user_id in range(1, NUM_USERS + 1):
        num_rolls = random.randint(1, MAX_ROLLS_PER_USER)
        tasks.append(simulate_user(user_id, num_rolls))

    # Run all user simulations concurrently
    await asyncio.gather(*tasks)

    # Give OTel time to export traces
    await asyncio.sleep(2)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Traffic generation complete in {duration:.2f} seconds")
    logging.info(
        "Check Tempo for distributed traces with 2-service spans (traffic-generator → dice-roller)"
    )


if __name__ == "__main__":
    asyncio.run(main())
