FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /opt/dian-release
COPY dist/release/ /opt/dian-release/
COPY release/manifest.json /opt/dian-release/approved-manifest.json
COPY scripts/verify_release.py /opt/dian-release/verify_release.py

# The bundle is reproduced from release/manifest.json before docker build.
# No source checkout, editable installation or dependency re-resolution is used.
RUN python verify_release.py --artifact-dir . --approved-manifest approved-manifest.json \
    && python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r requirements.lock \
    && python -m pip install --no-index --no-deps --require-hashes -r requirements-wheels.txt \
    && python -m pip check \
    && python -I verify_release.py --artifact-dir . --runtime

WORKDIR /app
EXPOSE 8000
CMD ["uvicorn", "facturacion_dian_api.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
