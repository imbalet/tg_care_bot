FROM ghcr.io/astral-sh/uv:python3.14-alpine

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src src

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["uvicorn", "tbank_mock.app:app", "--host", "0.0.0.0", "--port", "8080"]
