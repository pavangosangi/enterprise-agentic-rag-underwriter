FROM python:3.11-slim

WORKDIR /app

# Install basic system utils
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download models to cache in the image
COPY utility/init_models.py .
RUN python init_models.py

# Command to keep container running for development
CMD ["tail", "-f", "/dev/null"]
