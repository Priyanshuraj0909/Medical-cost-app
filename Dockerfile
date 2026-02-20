# ----------------------------
# Base image (Python 3.10 is safest for LightGBM)
# ----------------------------
FROM python:3.10-slim

# ----------------------------
# System dependencies for LightGBM
# ----------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Set working directory
# ----------------------------
WORKDIR /app

# ----------------------------
# Copy requirements first (for caching)
# ----------------------------
COPY requirements.txt .

# ----------------------------
# Install Python dependencies
# ----------------------------
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------
# Copy application code
# ----------------------------
COPY . .

# ----------------------------
# Expose FastAPI port
# ----------------------------
EXPOSE 8000

# ----------------------------
# Run FastAPI with Uvicorn
# ----------------------------
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
