FROM python:3.11-slim

# System dependencies for OpenCV + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU-only PyTorch FIRST (saves ~1.5 GB vs full CUDA version)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories and make everything writable
RUN mkdir -p uploads datasets && chmod -R 777 /app

# PORT is set by HF Spaces (7860), override for other platforms
ENV PORT=7860
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/status || exit 1

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "7860"]
