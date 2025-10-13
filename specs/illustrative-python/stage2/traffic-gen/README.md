# Traffic Generation for Stage 2

This script simulates frontend→backend requests with proper trace context propagation.

## Installation

Using `uv` (recommended):

```bash
# Create a virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

Or using standard pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

```bash
# Make sure Stage 2 is running
cd ../
docker compose ps

# Run traffic generation
python generate_traffic.py
```

## Configuration

Edit the script to change these parameters:
- `NUM_USERS`: Number of concurrent users (default: 10)
- `MAX_ROLLS_PER_USER`: Maximum rolls per user (default: 20)
- `BACKEND_URL`: Backend endpoint (default: http://localhost:8101)

## What it does

1. Simulates multiple concurrent users
2. Each user makes random number of roll requests
3. Creates spans with service name `traffic-generator`
4. Propagates trace context via W3C headers to backend
5. Results in distributed traces: traffic-generator → dice-roller

## Viewing traces

After running, check Tempo in Grafana:
- Navigate to Explore → Tempo
- Search by service name: `traffic-generator`
- Click on traces to see 2-service waterfall
