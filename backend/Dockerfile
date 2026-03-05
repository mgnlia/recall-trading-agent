FROM python:3.11-slim

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy ALL source FIRST — required before any install step
COPY . .

# Non-editable install from pyproject.toml (source already present above)
RUN uv pip install --system --no-cache .

EXPOSE 8000

CMD ["python", "main.py"]
