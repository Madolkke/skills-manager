FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY skillhub ./skillhub
COPY skillhub_worker ./skillhub_worker
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
EXPOSE 8000
CMD ["uvicorn", "skillhub.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
