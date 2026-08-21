FROM docker.io/library/python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
CMD ["./entrypoint.sh"]
