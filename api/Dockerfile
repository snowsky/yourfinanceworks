FROM python:3.13-slim

WORKDIR /app

# Install system dependencies (Debian/Ubuntu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    bash \
    libpq-dev \
    librdkafka-dev \
    libsasl2-dev \
    libssl-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
 && rm -rf /var/lib/apt/lists/*

# (Optional) Install Rust if needed for certain deps
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
 && echo 'export PATH=/root/.cargo/bin:$PATH' >> /root/.bashrc
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directory for database
RUN mkdir -p /app/data

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 