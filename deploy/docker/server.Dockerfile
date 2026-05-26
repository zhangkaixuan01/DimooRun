FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY apps ./apps
COPY migrations ./migrations
COPY packages ./packages
COPY scripts ./scripts

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/apps/server

EXPOSE 8000

CMD ["uvicorn", "dimoo_run.server:app", "--host", "0.0.0.0", "--port", "8000"]
