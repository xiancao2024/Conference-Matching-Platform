# 1. Use base image
FROM nvidia/cuda:12.2.0-base-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive

# 2. Add zstd to this block
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    curl \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# 3. Ollama install will not fail after that
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV CONFERENCE_DATA_PATH=/app/data/conference_kaggle.json

EXPOSE 8000

CMD ["/bin/bash", "-c", "ollama serve & sleep 5 && ollama run llama3.2:1b 'ready' && python3 server.py --host 0.0.0.0 --port 8000"]
