# Dockerfile for Odoo MCP Server with WeasyPrint support
# Based on proven working configurations from Railway/WeasyPrint deployments

FROM python:3.12-slim-bookworm

# Install WeasyPrint system dependencies via apt
# These are REQUIRED at runtime, not just build time
RUN apt-get update && apt-get install -y \
    # Core WeasyPrint dependencies
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    # GObject (the missing library causing errors)
    libgobject-2.0-0 \
    libgirepository-1.0-1 \
    # Additional required libraries
    libffi-dev \
    libglib2.0-0 \
    shared-mime-info \
    # Font support
    fonts-liberation \
    # Cleanup to reduce image size
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Railway will set PORT environment variable
# Default to 8001 if not set
ENV PORT=8001

# Start command will be overridden by Procfile in Railway
# But provide a default for local testing
CMD python odoo_mcp.py
