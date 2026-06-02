FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Lockfile + reproducible install (Resolución 165 supply-chain hardening).
# Mirror del approach de Pinki commit d74ce6a (31-may): el set de deps de
# terceros se resuelve con pip-compile/uv y los hashes se verifican en build.
COPY requirements.lock /app/requirements.lock

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-deps --require-hashes -r /app/requirements.lock

COPY packages/core /app/packages/core
COPY packages/server /app/packages/server

# Los dos packages locales se instalan en modo editable después; --no-deps
# evita que pip intente resolver de nuevo lo ya bloqueado.
RUN python -m pip install --no-deps -e /app/packages/core -e /app/packages/server

EXPOSE 8000

CMD ["uvicorn", "facturacion_dian_api.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
