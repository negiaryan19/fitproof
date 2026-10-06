FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /workspace
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

COPY backend/pyproject.toml backend/uv.lock ./backend/
COPY backend/app ./backend/app
COPY backend/fixtures ./backend/fixtures
RUN cd backend && uv sync --frozen --no-dev

WORKDIR /workspace/backend
EXPOSE 8017
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8017"]
