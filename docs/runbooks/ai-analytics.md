# Runbook: AI Analytics Service & Data Apps

## 1. Overview

This runbook covers operational procedures for:
1. Running the FastAPI backend service (`packages/ai_services`).
2. Running the Streamlit executive analytics dashboard (`packages/data_apps`).
3. Verifying PostgreSQL read-only credentials and role grants.
4. Diagnosing query timeouts and AST security rejections.

---

## 2. Environment Setup

Ensure environment variables are configured in `.env` (refer to `.env.example`):

```bash
# Database reader role
POSTGRES_READER_USER=analytics_reader
POSTGRES_READER_PASSWORD=analytics_reader_secret

# AI Provider settings
LLM_PROVIDER=mock
LLM_MODEL=gpt-4o-mini
```

---

## 3. Starting the FastAPI Backend

Launch the Uvicorn server hosting the AI Analytics API:

```bash
PYTHONPATH="packages/shared/src:packages/data_platform/src:packages/ai_services/src:packages/data_apps/src" \
  .venv/bin/uvicorn ai_services.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### Verification Endpoints

1. **Health Check**:
   ```bash
   curl -s http://localhost:8000/api/v1/analytics/health | jq
   ```
   *Expected Response:*
   ```json
   {
     "status": "UP",
     "database": "HEALTHY",
     "service": "ai_services",
     "version": "1.0.0"
   }
   ```

2. **Submit Analytical Inquiry**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/analytics/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "What was our total net recognized revenue?"}' | jq
   ```

3. **Explore OpenAPI Documentation**:
   Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.

---

## 4. Starting the Streamlit Dashboard

Run the Streamlit financial analytics interface:

```bash
PYTHONPATH="packages/shared/src:packages/data_platform/src:packages/ai_services/src:packages/data_apps/src" \
  .venv/bin/streamlit run packages/data_apps/src/data_apps/app.py --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501) in your browser to interact with the executive dashboard.

---

## 5. Troubleshooting & Diagnostics

### Issue 1: `permission denied for schema raw` or `metadata`
- **Cause**: An analytical query attempted to reference raw or catalog tables.
- **Resolution**: This is an intentional security control. The `analytics_reader` role is strictly restricted to schema `analytics`. Verify that the metric formula and generated SQL target certified marts (`analytics.fct_*`, `analytics.dim_*`).

### Issue 2: `Query execution cancelled: exceeded 5000ms statement timeout limit`
- **Cause**: The analytical query exceeded the 5-second statement limit due to large unindexed joins or table scans.
- **Resolution**:
  1. Inspect the SQL query in the response payload.
  2. Ensure customer filters or date range constraints (`assessed_date >= '2026-11-01'`) are supplied.
  3. Verify index coverage on foreign keys in PostgreSQL.

### Issue 3: `Query rejected by security boundary`
- **Cause**: The query contained forbidden tokens (e.g. `DROP`, `DELETE`, `UPDATE`), attempted to access disallowed schemas, or selected restricted columns (`password`, `secret`).
- **Resolution**: Check the specific AST validator rejection reason in the response payload.
