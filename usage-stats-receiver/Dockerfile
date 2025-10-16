FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project files
COPY pyproject.toml .
COPY main.py .

# Install dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# Expose port
EXPOSE 8000

# Run the scraper
CMD ["python", "main.py"]
