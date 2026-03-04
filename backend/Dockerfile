FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e "."

# Copy source
COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
