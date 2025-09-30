import random
import re
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# Instrument the app with Prometheus metrics
Instrumentator().instrument(app).expose(app)


@app.get("/roll/{dice}")
def roll_dice(dice: str):
    """
    Roll dice in XdY format (e.g., 3d6 rolls 3 six-sided dice).
    Returns JSON with total and individual rolls.
    """
    # Parse the dice notation
    match = re.match(r"^(\d+)d(\d+)$", dice.lower())
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid dice format. Use XdY where X and Y are positive integers (e.g., 3d6)"
        )

    num_dice = int(match.group(1))
    num_sides = int(match.group(2))

    # Validate positive integers
    if num_dice <= 0 or num_sides <= 0:
        raise HTTPException(
            status_code=400,
            detail="Both X and Y must be positive integers greater than 0"
        )

    # Roll the dice
    rolls = [random.randint(1, num_sides) for _ in range(num_dice)]
    total = sum(rolls)

    return {"total": total, "rolls": rolls}


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Dice Roller API - Use /roll/XdY to roll dice (e.g., /roll/2d6)"}