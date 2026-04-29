FROM python:3.11-slim

# System dependencies for OpenCV + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p uploads datasets && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# PORT is set by HF Spaces (7860), override for other platforms
ENV PORT=7860
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/status || exit 1

CMD python app.py --host 0.0.0.0 --port $PORT
