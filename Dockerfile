# ============================================
# Eco-Sentinel Full-Stack Dockerfile
# Multi-stage build: Frontend + Backend
# 1:1 copy of local environment to cloud
# ============================================

# ==========================================
# STAGE 1: Build Frontend (Vite)
# ==========================================
FROM node:20-slim AS frontend-builder

WORKDIR /build

# Copy package files first (better layer caching)
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci --silent

# Copy frontend source
COPY frontend/ ./

# Build production bundle
RUN npm run build

# ==========================================
# STAGE 2: Python Backend + Serve Frontend
# ==========================================
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

WORKDIR /app

# Install system dependencies required for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (better layer caching)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Credentials are supplied at runtime, never baked into the image.
COPY backend/ ./
RUN mkdir -p instance reports static/images/analysis

# Copy built frontend from Stage 1 into Flask static folder
COPY --from=frontend-builder /build/dist ./static/frontend

# Ensure proper permissions
RUN chmod -R 755 /app

# Expose port (Cloud Run uses PORT env variable)
EXPOSE 8080

# Start command using gunicorn
CMD exec gunicorn \
    --bind :${PORT:-8080} \
    --workers 1 \
    --threads 8 \
    --timeout 300 \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    "app:create_app()"
