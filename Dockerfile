# Use official Python slim image
FROM python:3.11-slim

# Install Tesseract OCR and image dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy all files to container
COPY . /app

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose port for Gunicorn
EXPOSE 10000

# Start app using Gunicorn
CMD ["gunicorn", "app:app", "--workers=1", "--threads=1", "--timeout=120"]

