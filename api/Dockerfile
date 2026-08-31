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
COPY log_config.json ./
RUN chmod +x entrypoint.sh
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["./entrypoint.sh"]
