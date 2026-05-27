FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY apps ./apps
COPY migrations ./migrations
COPY packages ./packages
COPY scripts ./scripts

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/apps/server

CMD ["python", "apps/worker/dimoo_run_worker/main.py"]
