#!/usr/bin/env python3
"""
Traffic generation script for Stage 1 Dice Roller API.

Simulates multiple concurrent users making dice roll requests.
"""

import asyncio
import httpx
import random
import logging
from datetime import datetime

# Configuration
NUM_USERS = 10
MAX_ROLLS_PER_USER = 20
BASE_URL = "http://localhost:8100"

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def simulate_user(user_id: int, num_rolls: int):
    """Simulate a single user making multiple dice roll requests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for roll_num in range(num_rolls):
            die_type = random.choice(["fair", "risky"])

            try:
                response = await client.get(
                    f"{BASE_URL}/roll", params={"die": die_type}
                )

                if response.status_code == 200:
                    result = response.json()
                    logging.info(
                        f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                        f"{die_type} -> {result['roll']}"
                    )
                else:
                    logging.warning(
                        f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                        f"{die_type} -> HTTP {response.status_code}"
                    )

            except httpx.TimeoutException:
                logging.error(
                    f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                    f"{die_type} -> TIMEOUT"
                )
            except Exception as e:
                logging.error(
                    f"User {user_id} roll {roll_num + 1}/{num_rolls}: "
                    f"{die_type} -> ERROR: {e}"
                )

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

    # Check if service is available
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(BASE_URL)
            if response.status_code != 200:
                logging.error(
                    f"Service not responding correctly: {response.status_code}"
                )
                return
            logging.info(f"Service available: {response.json()}")
    except Exception as e:
        logging.error(f"Service not available at {BASE_URL}: {e}")
        return

    # Create user simulation tasks
    tasks = []
    for user_id in range(1, NUM_USERS + 1):
        num_rolls = random.randint(1, MAX_ROLLS_PER_USER)
        tasks.append(simulate_user(user_id, num_rolls))

    # Run all user simulations concurrently
    await asyncio.gather(*tasks)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    logging.info(f"Traffic generation complete in {duration:.2f} seconds")


if __name__ == "__main__":
    asyncio.run(main())
