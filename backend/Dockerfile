FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy ALL source (must come before install so uv can resolve the local package)
COPY . .

# Install dependencies from pyproject.toml (non-editable, no source binding needed)
RUN uv pip install --system --no-cache .

EXPOSE 8000

CMD ["python", "main.py"]
