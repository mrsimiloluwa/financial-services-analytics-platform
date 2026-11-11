FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/packages/shared/src:/app/packages/data_platform/src:/app/packages/ai_services/src:/app/packages/data_apps/src"

# Install curl for healthchecks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml /app/
RUN pip install --no-cache-dir \
    "duckdb>=1.1.0" \
    "psycopg[binary]>=3.2.0" \
    "pydantic>=2.9.0" \
    "pydantic-settings>=2.5.0" \
    "dbt-core>=1.8.0" \
    "dbt-postgres>=1.8.0" \
    "fastapi>=0.115.0" \
    "uvicorn>=0.32.0" \
    "httpx>=0.27.0" \
    "langgraph>=0.2.0" \
    "streamlit>=1.40.0" \
    "sqlglot>=25.0.0"

# Copy application source code
COPY packages /app/packages

EXPOSE 8000 8501

CMD ["uvicorn", "ai_services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
