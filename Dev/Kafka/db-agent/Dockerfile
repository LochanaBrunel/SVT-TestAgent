# syntax=docker/dockerfile:1.4
FROM ubuntu:22.04

# Install all dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    libssl-dev \
    librdkafka-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Default command: open bash
CMD ["/bin/bash"]