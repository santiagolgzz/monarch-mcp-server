# Dockerfile for Monarch Money MCP Server
# Enables hosting the MCP server online for Claude mobile app integration

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    # Run from the project venv uv creates, so CMD needs no activation step.
    PATH="/app/.venv/bin:$PATH"

# uv, pinned by digest. The image installs from uv.lock rather than resolving
# at build time: dependency constraints in pyproject.toml are ranges, so a
# `pip install .` here would silently pull whatever is newest and bypass both
# the lockfile and the `exclude-newer` quarantine that decided it.
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /uvx /bin/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash mcpuser

WORKDIR /app

# Dependencies first, in their own layer: they change far less often than the
# source, so editing a tool does not re-resolve the whole environment.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-install-project --no-dev

# Then the project itself.
COPY src/ ./src/
RUN uv sync --locked --no-dev

# Create .mm directory for session storage
RUN mkdir -p /home/mcpuser/.mm && chown -R mcpuser:mcpuser /home/mcpuser/.mm

# Switch to non-root user
USER mcpuser

# Set HOME so the app writes to the right place
ENV HOME=/home/mcpuser

# Expose the default port
EXPOSE 8000

# Health check (respects PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Run the HTTP server
CMD ["monarch-mcp-http"]
