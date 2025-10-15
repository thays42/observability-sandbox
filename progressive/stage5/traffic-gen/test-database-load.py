#!/usr/bin/env python3
"""
Database load testing script for Stage 5.

Directly queries die-service endpoints at high rate to test database performance.
Measures query latency, throughput, and error rates.
"""

import asyncio
import httpx
import random
import logging
import time
from datetime import datetime
from collections import defaultdict
from typing import List, Dict

# Configuration
QUERIES_PER_SECOND = 50  # Target query rate
DURATION_SECONDS = 30  # How long to run the test
LIST_TO_GET_RATIO = 0.1  # Ratio of list queries vs get queries (1:10)
DIE_SERVICE_URL = "http://localhost:8109"  # Die service for stage5

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class PerformanceMetrics:
    """Track performance metrics during load test."""

    def __init__(self):
        self.query_count = 0
        self.error_count = 0
        self.latencies: List[float] = []
        self.query_types = defaultdict(int)
        self.status_codes = defaultdict(int)
        self.start_time = None
        self.end_time = None

    def record_query(self, query_type: str, latency: float, status_code: int):
        """Record a query execution."""
        self.query_count += 1
        self.latencies.append(latency)
        self.query_types[query_type] += 1
        self.status_codes[status_code] += 1

        if status_code >= 400:
            self.error_count += 1

    def get_percentile(self, p: float) -> float:
        """Calculate percentile from latencies."""
        if not self.latencies:
            return 0.0

        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * p)
        return sorted_latencies[index]

    def get_summary(self) -> Dict:
        """Get summary statistics."""
        duration = (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        qps = self.query_count / duration if duration > 0 else 0

        return {
            "total_queries": self.query_count,
            "errors": self.error_count,
            "error_rate": self.error_count / self.query_count if self.query_count > 0 else 0,
            "duration_seconds": duration,
            "queries_per_second": qps,
            "latency_p50_ms": self.get_percentile(0.50) * 1000,
            "latency_p95_ms": self.get_percentile(0.95) * 1000,
            "latency_p99_ms": self.get_percentile(0.99) * 1000,
            "query_types": dict(self.query_types),
            "status_codes": dict(self.status_codes),
        }


async def query_list(client: httpx.AsyncClient, metrics: PerformanceMetrics):
    """Query the list of all die identifiers."""
    start = time.time()

    try:
        response = await client.get(f"{DIE_SERVICE_URL}/dice")
        latency = time.time() - start

        metrics.record_query("list", latency, response.status_code)

        if response.status_code != 200:
            logging.warning(f"List query failed with status {response.status_code}")

    except Exception as e:
        latency = time.time() - start
        metrics.record_query("list", latency, 500)
        logging.error(f"List query error: {e}")


async def query_get(client: httpx.AsyncClient, metrics: PerformanceMetrics, identifier: str):
    """Query a specific die specification."""
    start = time.time()

    try:
        response = await client.get(f"{DIE_SERVICE_URL}/dice", params={"identifier": identifier})
        latency = time.time() - start

        metrics.record_query("get", latency, response.status_code)

        if response.status_code not in (200, 404):
            logging.warning(f"Get query for '{identifier}' failed with status {response.status_code}")

    except Exception as e:
        latency = time.time() - start
        metrics.record_query("get", latency, 500)
        logging.error(f"Get query error for '{identifier}': {e}")


async def run_load_test():
    """Run the database load test."""
    logging.info(f"Starting database load test for Stage 5")
    logging.info(f"Target: {QUERIES_PER_SECOND} queries/sec for {DURATION_SECONDS} seconds")
    logging.info(f"Die Service URL: {DIE_SERVICE_URL}")
    logging.info(f"List to Get ratio: {LIST_TO_GET_RATIO * 100:.0f}% list queries")

    # Check if die service is available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DIE_SERVICE_URL}/")
            if response.status_code == 200:
                logging.info(f"Die service is available")
            else:
                logging.warning(f"Die service returned status {response.status_code}")
    except Exception as e:
        logging.error(f"Cannot connect to die service: {e}")
        logging.info("Make sure Stage 5 is running: cd progressive/stage5 && docker compose up -d")
        return

    # Available die identifiers for testing
    die_identifiers = ["fair", "risky", "extreme", "unknown"]  # Include unknown for 404 testing

    # Calculate delay between queries to achieve target QPS
    delay_between_queries = 1.0 / QUERIES_PER_SECOND

    metrics = PerformanceMetrics()
    metrics.start_time = datetime.now()

    # Create HTTP client for duration of test
    async with httpx.AsyncClient(timeout=10.0) as client:
        test_end_time = time.time() + DURATION_SECONDS
        query_number = 0

        while time.time() < test_end_time:
            query_number += 1

            # Decide query type based on ratio
            if random.random() < LIST_TO_GET_RATIO:
                # List query
                await query_list(client, metrics)
            else:
                # Get query with random identifier
                identifier = random.choice(die_identifiers)
                await query_get(client, metrics, identifier)

            # Log progress every 100 queries
            if query_number % 100 == 0:
                elapsed = (datetime.now() - metrics.start_time).total_seconds()
                current_qps = query_number / elapsed if elapsed > 0 else 0
                logging.info(f"Progress: {query_number} queries, {current_qps:.1f} QPS, "
                            f"{metrics.error_count} errors")

            # Sleep to maintain target QPS
            await asyncio.sleep(delay_between_queries)

    metrics.end_time = datetime.now()

    # Print summary
    summary = metrics.get_summary()

    logging.info("=" * 60)
    logging.info("DATABASE LOAD TEST RESULTS")
    logging.info("=" * 60)
    logging.info(f"Total queries: {summary['total_queries']}")
    logging.info(f"Duration: {summary['duration_seconds']:.2f} seconds")
    logging.info(f"Achieved QPS: {summary['queries_per_second']:.2f}")
    logging.info(f"Target QPS: {QUERIES_PER_SECOND}")
    logging.info(f"QPS Achievement: {(summary['queries_per_second'] / QUERIES_PER_SECOND) * 100:.1f}%")
    logging.info("")
    logging.info(f"Errors: {summary['errors']}")
    logging.info(f"Error rate: {summary['error_rate'] * 100:.2f}%")
    logging.info("")
    logging.info(f"Latency P50: {summary['latency_p50_ms']:.2f} ms")
    logging.info(f"Latency P95: {summary['latency_p95_ms']:.2f} ms")
    logging.info(f"Latency P99: {summary['latency_p99_ms']:.2f} ms")
    logging.info("")
    logging.info(f"Query types: {summary['query_types']}")
    logging.info(f"Status codes: {summary['status_codes']}")
    logging.info("=" * 60)

    logging.info("")
    logging.info("Check database metrics in Grafana:")
    logging.info("  - Database query rate and duration")
    logging.info("  - Connection pool usage")
    logging.info("  - PostgreSQL metrics from postgres_exporter")


if __name__ == "__main__":
    asyncio.run(run_load_test())
