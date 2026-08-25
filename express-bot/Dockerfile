FROM docker.io/library/python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
ENV PYTHONUNBUFFERED=1
EXPOSE 8030
CMD ["sh", "-c", "uvicorn app.main:app --host ${BOT_LISTEN_HOST:-0.0.0.0} --port ${BOT_LISTEN_PORT:-8030}"]
