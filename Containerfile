# Build: podman build -t bring-mcp .
# Run:   podman run -d --name bring-mcp -p 127.0.0.1:8080:8080 --env-file bring.env bring-mcp
FROM docker.io/library/python:3.12-slim

# uv installs the project and its locked dependencies in one step.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv sync --locked --no-dev \
    && useradd --create-home --uid 10001 bring \
    && chown -R bring:bring /app

USER bring
ENV PATH="/app/.venv/bin:$PATH" \
    BRING_HTTP_HOST=0.0.0.0 \
    BRING_HTTP_PORT=8080

EXPOSE 8080
CMD ["bring-mcp", "serve-http"]
