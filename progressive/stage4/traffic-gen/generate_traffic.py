#!/usr/bin/env python3
"""
Traffic generation script for Stage 4 (with Async Rolling support).

Simulates multiple concurrent users making requests through the frontend.
Some users will choose async rolling based on ASYNC_PROBABILITY.
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
FRONTEND_URL = "http://localhost:8108"  # Frontend for stage4
OTEL_COLLECTOR_URL = "http://localhost:4318/v1/traces"

# Async rolling configuration
ASYNC_PROBABILITY = 0.3  # 30% chance of async rolling
MAX_ASYNC_ROLLS = 10  # Maximum number of dice in async batch

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Initialize OpenTelemetry tracing to simulate user traffic
resource = Resource(attributes={"service.name": "traffic-generator-stage4"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint=OTEL_COLLECTOR_URL)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer("traffic-generator")


async def simulate_user(user_id: int, num_requests: int):
    """Simulate a single user making multiple requests through frontend."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for request_num in range(num_requests):
            die_type = random.choice(["fair", "risky", "extreme", "unknown"])

            # Decide whether to use async rolling
            use_async = random.random() < ASYNC_PROBABILITY

            if use_async:
                # Async roll: pick random batch size
                times = random.randint(1, MAX_ASYNC_ROLLS)

                # Create a span to simulate user request
                with tracer.start_as_current_span(
                    "simulated_user_async_request",
                    attributes={
                        "user.id": user_id,
                        "die.type": die_type,
                        "request.number": request_num + 1,
                        "async.enabled": True,
                        "async.batch_size": times,
                    },
                ) as span:
                    # Inject trace context into headers
                    headers = {}
                    inject(headers)

                    try:
                        response = await client.get(
                            f"{FRONTEND_URL}/roll-async",
                            params={"die": die_type, "times": times},
                            headers=headers,
                        )

                        if response.status_code == 200:
                            result = response.json()
                            total = result.get("total")
                            rolls = result.get("rolls", [])
                            logging.info(
                                f"User {user_id} request {request_num + 1}/{num_requests}: "
                                f"ASYNC {die_type} x{times} -> total={total}, rolls={rolls}"
                            )
                            span.set_attribute("async.total_result", total)
                            span.set_attribute("request.status", "success")

                            # Log trace ID for easy lookup
                            if "trace_id" in result:
                                logging.debug(f"Trace ID: {result['trace_id']}")
                        else:
                            logging.warning(
                                f"User {user_id} request {request_num + 1}/{num_requests}: "
                                f"ASYNC {die_type} x{times} -> HTTP {response.status_code}"
                            )
                            span.set_attribute("request.status", "error")
                            span.set_attribute(
                                "response.status_code", response.status_code
                            )

                    except httpx.TimeoutException:
                        logging.error(
                            f"User {user_id} request {request_num + 1}/{num_requests}: "
                            f"ASYNC {die_type} x{times} -> TIMEOUT"
                        )
                        span.set_attribute("request.status", "timeout")
                    except Exception as e:
                        logging.error(
                            f"User {user_id} request {request_num + 1}/{num_requests}: "
                            f"ASYNC {die_type} x{times} -> ERROR: {e}"
                        )
                        span.set_attribute("request.status", "error")
                        span.set_attribute("error.message", str(e))
            else:
                # Sync roll (regular endpoint)
                # Create a span to simulate user request
                with tracer.start_as_current_span(
                    "simulated_user_sync_request",
                    attributes={
                        "user.id": user_id,
                        "die.type": die_type,
                        "request.number": request_num + 1,
                        "async.enabled": False,
                    },
                ) as span:
                    # Inject trace context into headers
                    headers = {}
                    inject(headers)

                    try:
                        response = await client.get(
                            f"{FRONTEND_URL}/roll",
                            params={"die": die_type},
                            headers=headers,
                        )

                        if response.status_code == 200:
                            result = response.json()
                            roll_value = result.get("roll")
                            logging.info(
                                f"User {user_id} request {request_num + 1}/{num_requests}: "
                                f"SYNC {die_type} -> {roll_value}"
                            )
                            span.set_attribute("roll.value", roll_value)
                            span.set_attribute("request.status", "success")

                            # Log trace ID for easy lookup
                            if "trace_id" in result:
                                logging.debug(f"Trace ID: {result['trace_id']}")
                        else:
                            logging.warning(
                                f"User {user_id} request {request_num + 1}/{num_requests}: "
                                f"SYNC {die_type} -> HTTP {response.status_code}"
                            )
                            span.set_attribute("request.status", "error")
                            span.set_attribute(
                                "response.status_code", response.status_code
                            )

                    except httpx.TimeoutException:
                        logging.error(
                            f"User {user_id} request {request_num + 1}/{num_requests}: "
                            f"SYNC {die_type} -> TIMEOUT"
                        )
                        span.set_attribute("request.status", "timeout")
                    except Exception as e:
                        logging.error(
                            f"User {user_id} request {request_num + 1}/{num_requests}: "
                            f"SYNC {die_type} -> ERROR: {e}"
                        )
                        span.set_attribute("request.status", "error")
                        span.set_attribute("error.message", str(e))

            # Random think time between requests (0.5-2 seconds)
            await asyncio.sleep(random.uniform(0.5, 2.0))

    logging.info(f"User {user_id} finished all {num_requests} requests")


async def main():
    """Main entry point for traffic generation."""
    start_time = datetime.now()
    logging.info(
        f"Starting traffic generation for Stage 4: {NUM_USERS} users, "
        f"up to {MAX_ROLLS_PER_USER} requests per user"
    )
    logging.info(
        f"Async probability: {ASYNC_PROBABILITY * 100:.0f}%, "
        f"max async batch size: {MAX_ASYNC_ROLLS}"
    )
    logging.info(
        f"Architecture: Traffic Generator → Frontend → Dice Roller → Die Service"
    )

    # Check if frontend is available
    logging.info(f"Connecting to frontend at {FRONTEND_URL}")
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0)
        ) as client:
            response = await client.get(f"{FRONTEND_URL}/roll", params={"die": "fair"})
            if response.status_code == 200:
                logging.info(f"Frontend available and responding to requests")
            else:
                logging.warning(
                    f"Frontend returned status {response.status_code}, continuing anyway..."
                )
    except httpx.ConnectError as e:
        logging.error(f"Cannot connect to frontend at {FRONTEND_URL}: {e}")
        logging.info(
            "Make sure Stage 4 is running: cd specs/illustrative-python/stage4 && docker compose up -d"
        )
        return
    except Exception as e:
        logging.warning(f"Health check failed ({e}), but will try to continue...")

    # Create user simulation tasks
    tasks = []
    for user_id in range(1, NUM_USERS + 1):
        num_requests = random.randint(1, MAX_ROLLS_PER_USER)
        tasks.append(simulate_user(user_id, num_requests))

    # Run all user simulations concurrently
    await asyncio.gather(*tasks)

    # Give OTel time to export traces
    await asyncio.sleep(2)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Traffic generation complete in {duration:.2f} seconds")
    logging.info("Check Grafana → Explore → Tempo for distributed traces:")
    logging.info(
        "  - Sync traces: traffic-generator → frontend → dice-roller → die-service"
    )
    logging.info(
        "  - Async traces: Look for traces with concurrent child spans in dice-roller service"
    )


if __name__ == "__main__":
    asyncio.run(main())
