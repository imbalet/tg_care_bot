FROM ghcr.io/astral-sh/uv:python3.14-alpine AS russian-ca

ARG RUSSIAN_TRUSTED_ROOT_CA_URL=https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer
ARG RUSSIAN_TRUSTED_ROOT_CA_SHA256=936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504
ARG RUSSIAN_TRUSTED_SUB_CA_URL=https://gu-st.ru/content/Other/doc/russian_trusted_sub_ca.cer
ARG RUSSIAN_TRUSTED_SUB_CA_SHA256=f0ae589f36774f29ef3648f7984b08d42fcce6f1ffeeb6236d773daeb2744ea6

RUN apk add --no-cache ca-certificates curl openssl \
    && mkdir -p /tmp/russian-ca /russian-ca \
    && curl --fail --location --silent --show-error --insecure --tlsv1.2 \
        "$RUSSIAN_TRUSTED_ROOT_CA_URL" \
        --output /tmp/russian-ca/root.cer \
    && curl --fail --location --silent --show-error --insecure --tlsv1.2 \
        "$RUSSIAN_TRUSTED_SUB_CA_URL" \
        --output /tmp/russian-ca/sub.cer \
    && echo "$RUSSIAN_TRUSTED_ROOT_CA_SHA256  /tmp/russian-ca/root.cer" | sha256sum -c - \
    && echo "$RUSSIAN_TRUSTED_SUB_CA_SHA256  /tmp/russian-ca/sub.cer" | sha256sum -c - \
    && if openssl x509 -in /tmp/russian-ca/root.cer -noout >/dev/null 2>&1; then \
        cp /tmp/russian-ca/root.cer /russian-ca/russian_trusted_root_ca.crt; \
    else \
        openssl x509 -inform DER -in /tmp/russian-ca/root.cer \
            -out /russian-ca/russian_trusted_root_ca.crt; \
    fi \
    && if openssl x509 -in /tmp/russian-ca/sub.cer -noout >/dev/null 2>&1; then \
        cp /tmp/russian-ca/sub.cer /russian-ca/russian_trusted_sub_ca.crt; \
    else \
        openssl x509 -inform DER -in /tmp/russian-ca/sub.cer \
            -out /russian-ca/russian_trusted_sub_ca.crt; \
    fi \
    && openssl x509 -in /russian-ca/russian_trusted_root_ca.crt -noout \
        -subject -issuer \
    && openssl x509 -in /russian-ca/russian_trusted_sub_ca.crt -noout \
        -subject -issuer \
    && test "$(openssl x509 -in /russian-ca/russian_trusted_root_ca.crt -noout -subject)" \
        = "subject=C=RU, O=The Ministry of Digital Development and Communications, CN=Russian Trusted Root CA" \
    && test "$(openssl x509 -in /russian-ca/russian_trusted_sub_ca.crt -noout -subject)" \
        = "subject=C=RU, O=The Ministry of Digital Development and Communications, CN=Russian Trusted Sub CA" \
    && test "$(openssl x509 -in /russian-ca/russian_trusted_sub_ca.crt -noout -issuer)" \
        = "issuer=C=RU, O=The Ministry of Digital Development and Communications, CN=Russian Trusted Root CA"

FROM ghcr.io/astral-sh/uv:python3.14-alpine AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY pyproject.toml uv.lock README.md ./
COPY alembic.ini alembic.ini
COPY alembic alembic
COPY src src
COPY templates templates

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.14-alpine

RUN apk add --no-cache ca-certificates \
    && adduser -S -u 999 nonroot

COPY --from=russian-ca /russian-ca/ /usr/local/share/ca-certificates/

RUN update-ca-certificates

COPY --from=builder --chown=nonroot:nonroot /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    SSL_CERT_FILE="/etc/ssl/certs/ca-certificates.crt" \
    REQUESTS_CA_BUNDLE="/etc/ssl/certs/ca-certificates.crt"

USER nonroot
WORKDIR /app

CMD ["uvicorn", "backend.bootstrap.api:app", "--host", "0.0.0.0", "--port", "8000"]
