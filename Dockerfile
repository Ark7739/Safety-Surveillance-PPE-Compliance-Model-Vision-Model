FROM python:3.11-slim

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install ALL Python deps in one layer (CPU-only PyTorch + requirements)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code only
COPY app.py wsgi.py data.yaml ./
COPY models/ ./models/
COPY static/ ./static/
COPY scripts/ ./scripts/

# Create writable directories
RUN mkdir -p uploads datasets && chmod -R 777 /app

EXPOSE 7860

CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "7860"]
