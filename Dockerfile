# ======================= BUILD STAGE =======================
FROM python:3.11-slim AS build

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git gcc build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python build dependencies
RUN pip install --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Copy only the requirements first for caching
# This makes it so that we only re-install dependencies (which is slow) if they change
COPY requirements.txt .

# Install Python dependencies in a virtualenv
RUN python -m venv /venv && \
    /venv/bin/pip install -r requirements.txt

# Copy the full source code (after installing requirements to keep caching effective)
COPY . /app


# ======================= BUILD STAGE =======================
FROM python:3.11-slim AS runtime

# Install runtime-only dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Copy virtual environment and application code from builder
COPY --from=build /venv /venv
COPY --from=build /app /app

# Activate virtualenv
ENV PATH="/venv/bin:$PATH"

WORKDIR /app

EXPOSE 4200

CMD ["python", "run.py"]
