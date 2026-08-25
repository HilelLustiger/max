FROM python:3.12-slim

RUN pip install --no-cache-dir uv

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY DB DB
COPY Agent Agent

RUN uv sync --frozen --package agent

WORKDIR /workspace
EXPOSE 8000
CMD ["uv", "run", "--package", "agent", "uvicorn", "app.main:app", "--app-dir", "Agent", "--host", "0.0.0.0", "--port", "8000"]
