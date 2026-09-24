FROM node:24.18.0-bookworm-slim AS web-build
WORKDIR /build
COPY apps/web/package.json apps/web/package-lock.json ./apps/web/
RUN npm ci --ignore-scripts --prefix apps/web
COPY apps/web ./apps/web
RUN npm run --prefix apps/web typecheck \
    && npm run --prefix apps/web lint \
    && npm run --prefix apps/web test \
    && npm run --prefix apps/web build

FROM python:3.14.6-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    SSL_TBANK_VERIFY=True
WORKDIR /app

RUN groupadd --system omni && useradd --system --gid omni --home-dir /app omni
COPY requirements.txt ./requirements.txt
COPY scripts/prepare_v10_tbank_pip_ca_bundle.py ./scripts/prepare_v10_tbank_pip_ca_bundle.py
COPY docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json ./docs/architecture/V10_TBANK_CA_TRUST_CONTRACT.json
COPY infrastructure/certificates/russian_trusted_root_ca_2022.der ./infrastructure/certificates/russian_trusted_root_ca_2022.der
RUN set -eu; \
    export RUNNER_TEMP=/tmp; \
    python scripts/prepare_v10_tbank_pip_ca_bundle.py > /tmp/tbank-pip-ca.json; \
    PIP_CERT_PATH="$(python -c \
        'import json; print(json.load(open("/tmp/tbank-pip-ca.json", encoding="utf-8"))["bundle_path"])')"; \
    test -f "$PIP_CERT_PATH"; \
    PIP_CERT="$PIP_CERT_PATH" python -m pip install \
        --only-binary=:all: --require-hashes -r requirements.txt; \
    rm -f "$PIP_CERT_PATH" /tmp/tbank-pip-ca.json

COPY apps ./apps
COPY omni_cio ./omni_cio
COPY --from=web-build /build/apps/web/dist ./apps/web/dist
RUN test -s apps/web/dist/index.html && chown -R omni:omni /app

USER omni
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/livez', timeout=3).read()" || exit 1

CMD ["python", "-m", "uvicorn", "apps.api.hosted_runtime:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
