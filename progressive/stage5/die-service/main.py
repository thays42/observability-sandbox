import logging
import json
import os
import time
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

import asyncpg


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

# Instrument asyncpg for automatic database tracing
AsyncPGInstrumentor().instrument()

# Create FastAPI app
app = FastAPI(title="Die Service API", version="2.0.0")

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
    "Number of die specifications loaded in database",
)

# Database-specific metrics
database_queries_total = Counter(
    "database_queries_total",
    "Total number of database queries",
    ["query_type", "result"],
)

database_query_duration_seconds = Histogram(
    "database_query_duration_seconds",
    "Duration of database queries in seconds",
    ["query_type"],
)

database_connection_pool_size = Gauge(
    "database_connection_pool_size",
    "Size of the database connection pool",
)

database_connection_pool_available = Gauge(
    "database_connection_pool_available",
    "Number of available connections in the pool",
)

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None


async def get_database_url() -> str:
    """Get database URL from environment variable."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://diceuser:dicepass@postgres:5432/dicedb"
    )


async def init_db_pool():
    """Initialize database connection pool."""
    global db_pool

    database_url = await get_database_url()

    try:
        logger.info("Initializing database connection pool")

        db_pool = await asyncpg.create_pool(
            database_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )

        # Update pool metrics
        database_connection_pool_size.set(10)  # max_size

        logger.info(
            "Database connection pool established",
            extra={
                "extra_fields": {
                    "min_size": 2,
                    "max_size": 10,
                }
            },
        )

        # Get initial count of specifications
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM die_specifications")
            die_specifications_loaded.set(count)

            logger.info(
                "Database seeded with die specifications",
                extra={"extra_fields": {"count": count}},
            )

        return True

    except Exception as e:
        logger.error(
            "Database connection failed",
            extra={"extra_fields": {"error": str(e)}},
        )
        return False


async def close_db_pool():
    """Close database connection pool."""
    global db_pool

    if db_pool:
        await db_pool.close()
        logger.info("Database connection pool closed")


@app.on_event("startup")
async def startup_event():
    logger.info("Die Service API starting up")

    # Initialize database connection pool
    if not await init_db_pool():
        logger.warning(
            "Failed to initialize database - service may not work correctly"
        )


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Die Service API shutting down")
    await close_db_pool()


@app.get("/")
async def root():
    """Root endpoint with service information."""
    try:
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM die_specifications")

        return {
            "service": "Die Service API",
            "version": "2.0.0",
            "endpoints": ["/dice", "/dice?identifier={id}"],
            "loaded_specifications": count,
            "database": "PostgreSQL",
        }
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        return {
            "service": "Die Service API",
            "version": "2.0.0",
            "endpoints": ["/dice", "/dice?identifier={id}"],
            "database": "PostgreSQL (error)",
            "error": str(e),
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
        query_type = "list"
        span.set_attribute("request.type", query_type)
        span.set_attribute("db.query_type", query_type)

        start_time = time.time()

        try:
            async with db_pool.acquire() as conn:
                # Update pool metrics
                database_connection_pool_available.set(db_pool.get_size() - db_pool.get_size())

                rows = await conn.fetch("SELECT identifier FROM die_specifications ORDER BY identifier")
                identifiers = [row["identifier"] for row in rows]

            duration = time.time() - start_time
            database_query_duration_seconds.labels(query_type=query_type).observe(duration)
            database_queries_total.labels(query_type=query_type, result="success").inc()

            die_list_requests_total.inc()
            span.set_attribute("die.count", len(identifiers))

            logger.info(
                "Die list requested",
                extra={
                    "extra_fields": {
                        "count": len(identifiers),
                        "identifiers": identifiers,
                        "db_query_duration_ms": duration * 1000,
                    }
                },
            )

            return {"identifiers": identifiers}

        except Exception as e:
            duration = time.time() - start_time
            database_query_duration_seconds.labels(query_type=query_type).observe(duration)
            database_queries_total.labels(query_type=query_type, result="error").inc()

            logger.error(
                "Database query failed",
                extra={
                    "extra_fields": {
                        "query_type": query_type,
                        "error": str(e),
                    }
                },
            )
            raise HTTPException(status_code=500, detail="Database query failed")

    else:
        # Return specific die specification
        query_type = "get"
        span.set_attribute("request.type", query_type)
        span.set_attribute("die.identifier", identifier)
        span.set_attribute("db.query_type", query_type)

        logger.info(
            "Die specification requested",
            extra={"extra_fields": {"identifier": identifier}},
        )

        start_time = time.time()

        try:
            async with db_pool.acquire() as conn:
                # Update pool metrics
                database_connection_pool_available.set(db_pool.get_size() - db_pool.get_size())

                row = await conn.fetchrow(
                    "SELECT identifier, faces, error_rate FROM die_specifications WHERE identifier = $1",
                    identifier
                )

            duration = time.time() - start_time
            database_query_duration_seconds.labels(query_type=query_type).observe(duration)

            if row:
                database_queries_total.labels(query_type=query_type, result="success").inc()
                die_specifications_requested_total.labels(identifier=identifier).inc()
                span.set_attribute("die.found", True)

                spec = {
                    "faces": row["faces"],
                    "error_rate": row["error_rate"],
                }

                logger.info(
                    "Die specification found",
                    extra={
                        "extra_fields": {
                            "identifier": identifier,
                            "faces": spec["faces"],
                            "error_rate": spec["error_rate"],
                            "db_query_duration_ms": duration * 1000,
                        }
                    },
                )

                return {
                    "identifier": identifier,
                    "specification": spec,
                }
            else:
                database_queries_total.labels(query_type=query_type, result="success").inc()
                span.set_attribute("die.found", False)

                # Get available identifiers for error message
                async with db_pool.acquire() as conn:
                    rows = await conn.fetch("SELECT identifier FROM die_specifications ORDER BY identifier")
                    available = [r["identifier"] for r in rows]

                logger.warning(
                    "Unknown die identifier requested",
                    extra={
                        "extra_fields": {
                            "identifier": identifier,
                            "available_identifiers": available,
                        }
                    },
                )

                raise HTTPException(
                    status_code=404,
                    detail=f"Die identifier '{identifier}' not found. Available: {available}",
                )

        except HTTPException:
            raise
        except Exception as e:
            duration = time.time() - start_time
            database_query_duration_seconds.labels(query_type=query_type).observe(duration)
            database_queries_total.labels(query_type=query_type, result="error").inc()

            logger.error(
                "Database query failed",
                extra={
                    "extra_fields": {
                        "query_type": query_type,
                        "identifier": identifier,
                        "error": str(e),
                    }
                },
            )
            raise HTTPException(status_code=500, detail="Database query failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
