FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Copy the project files
COPY pyproject.toml uv.lock ./
COPY main.py ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose the port
EXPOSE 8001

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]