import logging
import json
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import psycopg2
from psycopg2.extras import Json
import os
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("usage-stats-scraper")

# Configuration
LOKI_URL = os.getenv("LOKI_URL", "http://loki:3100")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))  # 1 minute default
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "2"))  # Look back 2 minutes to avoid missing logs

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "postgres"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "database": os.getenv("POSTGRES_DB", "usage_stats"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}

# Track last processed timestamp to avoid duplicates
last_processed_timestamp = None


def get_db_connection():
    """Create a database connection."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def query_loki_for_usage_logs(start_time: datetime, end_time: datetime) -> list:
    """
    Query Loki for logs with usage=true.

    Returns list of log entries with their labels and data.
    """
    try:
        # Build LogQL query - find logs with usage=true
        logql_query = '{job=~".+"} | json | usage="true"'

        # Convert times to nanoseconds (Loki format)
        start_ns = int(start_time.timestamp() * 1e9)
        end_ns = int(end_time.timestamp() * 1e9)

        # Query Loki
        params = {
            'query': logql_query,
            'start': start_ns,
            'end': end_ns,
            'limit': 5000,  # Max logs per query
        }

        url = f"{LOKI_URL}/loki/api/v1/query_range"
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            logger.error(f"Loki query failed: {response.status_code} - {response.text}")
            return []

        data = response.json()

        # Parse results
        log_entries = []
        if data.get('status') == 'success':
            results = data.get('data', {}).get('result', [])

            for result in results:
                labels = result.get('stream', {})
                values = result.get('values', [])

                for value in values:
                    timestamp_ns = value[0]
                    log_line = value[1]

                    try:
                        # Parse log line as JSON
                        log_data = json.loads(log_line)

                        # Only process if usage=true (double-check)
                        if log_data.get('usage') == True:
                            log_entries.append({
                                'timestamp_ns': timestamp_ns,
                                'labels': labels,
                                'data': log_data
                            })
                    except json.JSONDecodeError:
                        # Skip non-JSON logs
                        continue

            logger.info(f"Found {len(log_entries)} usage log entries from Loki")
        else:
            logger.warning(f"Loki query returned status: {data.get('status')}")

        return log_entries

    except Exception as e:
        logger.error(f"Error querying Loki: {e}")
        return []


def store_usage_stats(log_entries: list) -> int:
    """
    Store usage log entries in PostgreSQL.
    Returns number of records inserted.
    """
    if not log_entries:
        return 0

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        inserted_count = 0

        for entry in log_entries:
            labels = entry['labels']
            log_data = entry['data']
            timestamp_ns = entry['timestamp_ns']

            # Extract application from labels
            application = labels.get('compose_service', 'unknown')

            # Create full log event structure
            log_event = {
                'timestamp': timestamp_ns,
                'labels': labels,
                'data': log_data
            }

            # Check if this exact log already exists (by timestamp and data)
            # to avoid duplicates
            cursor.execute(
                "SELECT id FROM usage_stats WHERE data->>'timestamp' = %s AND application = %s LIMIT 1",
                (timestamp_ns, application)
            )

            if cursor.fetchone():
                # Already exists, skip
                continue

            # Insert into database
            cursor.execute(
                "INSERT INTO usage_stats (data, application) VALUES (%s, %s) RETURNING id",
                (Json(log_event), application)
            )

            record_id = cursor.fetchone()[0]
            inserted_count += 1

            logger.debug(f"Stored usage stat id={record_id} for application='{application}'")

        conn.commit()
        cursor.close()
        conn.close()

        if inserted_count > 0:
            logger.info(f"Inserted {inserted_count} new usage stats records")

        return inserted_count

    except Exception as e:
        logger.error(f"Error storing usage stats: {e}")
        if conn:
            conn.rollback()
        return 0


async def scrape_loop():
    """
    Main scraping loop - queries Loki periodically and stores results.
    """
    global last_processed_timestamp

    logger.info(f"Starting usage stats scraper (polling every {POLL_INTERVAL}s)")
    logger.info(f"Loki URL: {LOKI_URL}")
    logger.info(f"Lookback window: {LOOKBACK_MINUTES} minutes")

    while True:
        try:
            # Determine time range to query
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=LOOKBACK_MINUTES)

            logger.debug(f"Querying Loki from {start_time} to {end_time}")

            # Query Loki
            log_entries = query_loki_for_usage_logs(start_time, end_time)

            # Store in PostgreSQL
            if log_entries:
                inserted = store_usage_stats(log_entries)
                if inserted > 0:
                    logger.info(f"Successfully processed {inserted} usage stats")
            else:
                logger.debug("No new usage logs found")

            # Update last processed timestamp
            last_processed_timestamp = end_time

        except Exception as e:
            logger.error(f"Error in scrape loop: {e}")

        # Wait before next poll
        await asyncio.sleep(POLL_INTERVAL)


def main():
    """Main entry point."""
    logger.info("Usage Stats Scraper starting up")

    # Test database connection
    try:
        conn = get_db_connection()
        conn.close()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        exit(1)

    # Test Loki connection
    try:
        response = requests.get(f"{LOKI_URL}/ready", timeout=5)
        if response.status_code == 200:
            logger.info("Loki connection successful")
        else:
            logger.warning(f"Loki health check returned: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to connect to Loki: {e}")
        exit(1)

    # Start scraping loop
    asyncio.run(scrape_loop())


if __name__ == "__main__":
    main()
