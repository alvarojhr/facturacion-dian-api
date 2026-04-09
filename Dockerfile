FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY packages/core /app/packages/core
COPY packages/server /app/packages/server

RUN python -m pip install --upgrade pip \
    && python -m pip install -e /app/packages/core -e /app/packages/server

EXPOSE 8000

CMD ["uvicorn", "facturacion_dian_kit.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
