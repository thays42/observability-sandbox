#!/usr/bin/env python3
"""
Performance comparison script for Stage 4.

Compares performance between:
1. 10 sequential /roll calls
2. 1 /roll-async call with times=10

Measures total time and calculates speedup factor.
"""

import asyncio
import httpx
import time
import logging
from statistics import mean, stdev

# Configuration
DICE_ROLLER_URL = "http://localhost:8107"  # Direct to dice-roller for stage4
DIE_TYPE = "fair"
NUM_ROLLS = 10
NUM_ITERATIONS = 5  # Run test multiple times for statistical significance

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def test_sequential_rolls(client: httpx.AsyncClient, num_rolls: int) -> float:
    """
    Test sequential roll performance.
    Makes num_rolls separate requests to /roll endpoint.
    """
    start_time = time.time()

    for i in range(num_rolls):
        try:
            response = await client.get(
                f"{DICE_ROLLER_URL}/roll", params={"die": DIE_TYPE}
            )
            if response.status_code != 200:
                logging.warning(
                    f"Sequential roll {i + 1} returned status {response.status_code}"
                )
        except Exception as e:
            logging.error(f"Sequential roll {i + 1} failed: {e}")
            return -1

    duration = time.time() - start_time
    return duration


async def test_async_batch_roll(client: httpx.AsyncClient, num_rolls: int) -> float:
    """
    Test async batch roll performance.
    Makes 1 request to /roll-async endpoint with times=num_rolls.
    """
    start_time = time.time()

    try:
        response = await client.get(
            f"{DICE_ROLLER_URL}/roll-async",
            params={"die": DIE_TYPE, "times": num_rolls},
        )
        if response.status_code != 200:
            logging.warning(f"Async batch roll returned status {response.status_code}")
            return -1

        result = response.json()
        logging.debug(f"Async result: total={result['total']}, rolls={result['rolls']}")
    except Exception as e:
        logging.error(f"Async batch roll failed: {e}")
        return -1

    duration = time.time() - start_time
    return duration


async def run_performance_test():
    """Run the performance comparison test."""
    logging.info("=" * 70)
    logging.info("Stage 4: Async Rolling Performance Test")
    logging.info("=" * 70)
    logging.info(f"Dice Roller URL: {DICE_ROLLER_URL}")
    logging.info(f"Die type: {DIE_TYPE}")
    logging.info(f"Number of rolls: {NUM_ROLLS}")
    logging.info(f"Test iterations: {NUM_ITERATIONS}")
    logging.info("")

    # Check if dice roller is available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DICE_ROLLER_URL}/")
            if response.status_code == 200:
                data = response.json()
                logging.info(
                    f"Connected to: {data.get('service')} v{data.get('version')}"
                )
                logging.info(f"Stage: {data.get('stage')}")
                logging.info("")
            else:
                logging.error(f"Dice roller returned status {response.status_code}")
                return
    except Exception as e:
        logging.error(f"Cannot connect to dice roller at {DICE_ROLLER_URL}: {e}")
        logging.info(
            "Make sure Stage 4 is running: cd specs/illustrative-python/stage4 && docker compose up -d"
        )
        return

    sequential_times = []
    async_times = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for iteration in range(NUM_ITERATIONS):
            logging.info(f"Iteration {iteration + 1}/{NUM_ITERATIONS}")
            logging.info("-" * 70)

            # Test sequential rolls
            logging.info(f"Testing sequential: {NUM_ROLLS} separate /roll calls...")
            seq_duration = await test_sequential_rolls(client, NUM_ROLLS)
            if seq_duration > 0:
                sequential_times.append(seq_duration)
                logging.info(f"✓ Sequential completed in {seq_duration:.3f} seconds")
            else:
                logging.error("✗ Sequential test failed")

            # Small delay between tests
            await asyncio.sleep(1)

            # Test async batch roll
            logging.info(f"Testing async: 1 /roll-async call with times={NUM_ROLLS}...")
            async_duration = await test_async_batch_roll(client, NUM_ROLLS)
            if async_duration > 0:
                async_times.append(async_duration)
                logging.info(f"✓ Async completed in {async_duration:.3f} seconds")
            else:
                logging.error("✗ Async test failed")

            if seq_duration > 0 and async_duration > 0:
                speedup = seq_duration / async_duration
                logging.info(f"→ Speedup for this iteration: {speedup:.2f}x")

            logging.info("")

            # Delay between iterations
            await asyncio.sleep(2)

    # Calculate statistics
    logging.info("=" * 70)
    logging.info("Results Summary")
    logging.info("=" * 70)

    if sequential_times and async_times:
        seq_mean = mean(sequential_times)
        async_mean = mean(async_times)
        overall_speedup = seq_mean / async_mean

        logging.info(f"\nSequential Rolls ({NUM_ROLLS} separate calls):")
        logging.info(f"  Mean:   {seq_mean:.3f} seconds")
        if len(sequential_times) > 1:
            logging.info(f"  StdDev: {stdev(sequential_times):.3f} seconds")
        logging.info(f"  Min:    {min(sequential_times):.3f} seconds")
        logging.info(f"  Max:    {max(sequential_times):.3f} seconds")

        logging.info(f"\nAsync Batch Roll (1 call with times={NUM_ROLLS}):")
        logging.info(f"  Mean:   {async_mean:.3f} seconds")
        if len(async_times) > 1:
            logging.info(f"  StdDev: {stdev(async_times):.3f} seconds")
        logging.info(f"  Min:    {min(async_times):.3f} seconds")
        logging.info(f"  Max:    {max(async_times):.3f} seconds")

        logging.info(f"\n{'🚀 Performance Improvement 🚀':^70}")
        logging.info(f"{'=' * 70}")
        logging.info(
            f"\n  Async rolling is {overall_speedup:.2f}x FASTER than sequential!\n"
        )
        logging.info(
            f"  Time saved: {seq_mean - async_mean:.3f} seconds ({((seq_mean - async_mean) / seq_mean * 100):.1f}%)"
        )
        logging.info("")

        # Explanation
        logging.info("Why is async faster?")
        logging.info(
            "  Sequential: Each roll waits for previous to complete (sequential delays add up)"
        )
        logging.info(
            "  Async:      All rolls execute concurrently (delays happen in parallel)"
        )
        logging.info("")
        logging.info("Check Grafana → Explore → Tempo:")
        logging.info(
            "  Search for async traces to see overlapping child spans in the waterfall view"
        )
        logging.info("=" * 70)

    else:
        logging.error("Not enough successful test runs to calculate statistics")


async def main():
    await run_performance_test()


if __name__ == "__main__":
    asyncio.run(main())
