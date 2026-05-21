# python:3.13-slim (Debian/glibc) is intentional — LanceDB and PyArrow ship
# glibc-only (manylinux) wheels that are incompatible with Alpine's musl libc.
FROM python:3.13-slim AS builder

RUN pip install poetry==2.3.2

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-interaction --no-ansi --no-cache --no-root \
  --no-directory --only main

COPY ./src /app/src


FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN adduser --uid 1001 --disabled-password --gecos "" appuser
COPY --chown=appuser --from=builder /app .

RUN echo '#!/bin/sh' > /docker_entrypoint.sh && \
    echo 'set -e' >> /docker_entrypoint.sh && \
    echo '. ./.venv/bin/activate' >> /docker_entrypoint.sh && \
    echo 'exec "$@"' >> /docker_entrypoint.sh && \
    chmod +x /docker_entrypoint.sh

EXPOSE 8000

USER appuser
ENTRYPOINT ["/docker_entrypoint.sh"]

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
  CMD curl -sf http://localhost:8000/v1/configuration-support/application-schema || exit 1

CMD ["python", "-m", "src.main"]
