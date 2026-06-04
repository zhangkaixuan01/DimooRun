FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY apps ./apps
COPY examples ./examples
COPY migrations ./migrations
COPY packages ./packages
COPY scripts ./scripts

RUN pip install --no-cache-dir .

ENV PYTHONPATH=/app/apps/server

EXPOSE 8000

CMD ["python", "-m", "dimoo_run.ops.docker_entrypoint"]
