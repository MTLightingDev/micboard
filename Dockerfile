FROM python:3.11-slim

LABEL maintainer="karlcswanson@gmail.com"

WORKDIR /usr/src/app

# Install dependencies for Node.js setup
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    build-essential \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy package files first to leverage caching
COPY package*.json ./
RUN npm install --only=production

# Copy requirements and install python dependencies
COPY py/requirements.txt ./py/
RUN pip install --no-cache-dir -r py/requirements.txt

# Copy the rest of the application
COPY . .

# Build the frontend
RUN npm run build

# Expose port
EXPOSE 8058

# Set command
CMD ["python3", "py/micboard.py"]
