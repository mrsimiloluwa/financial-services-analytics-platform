# Application Operations Runbook

## 1. Quick Start & Execution

### 1.1 Running Locally with Virtual Environment

Ensure the PostgreSQL container is running:
```bash
docker compose up -d postgres
```

#### Starting the FastAPI Backend
```bash
PYTHONPATH="packages/shared/src:packages/data_platform/src:packages/ai_services/src:packages/data_apps/src" \
.venv/bin/uvicorn ai_services.api.app:app --host 127.0.0.1 --port 8000 --reload
```

#### Starting the Streamlit Executive Dashboard
```bash
PYTHONPATH="packages/shared/src:packages/data_platform/src:packages/ai_services/src:packages/data_apps/src" \
.venv/bin/streamlit run packages/data_apps/src/data_apps/app.py --server.port 8501
```

Once running:
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Streamlit Executive Dashboard**: [http://localhost:8501](http://localhost:8501)

---

### 1.2 Running via Docker Compose

To start the complete platform including PostgreSQL, Apache Airflow, FastAPI, and Streamlit:
```bash
docker compose up -d
```

To start only the application services (PostgreSQL, FastAPI, and Streamlit):
```bash
docker compose up -d postgres api dashboard
```

To inspect container statuses:
```bash
docker compose ps
```

---

## 2. API Endpoint Testing & Verification

### 2.1 Health Probe
```bash
curl -s http://localhost:8000/health | jq .
```
Expected output:
```json
{
  "status": "UP",
  "database": "HEALTHY",
  "database_latency_ms": 1.45,
  "environment": "dev",
  "version": "1.0.0",
  "components": {
    "postgresql": "UP",
    "analytics_reader": "UP",
    "metadata_service": "UP"
  }
}
```

### 2.2 Reconciled Financial Overview
```bash
curl -s "http://localhost:8000/api/v1/analytics/overview?environment=dev" | jq .
```
Key response values to verify:
* `net_recognized_revenue_eur`: `408602.64`
* `uncollected_arrears_eur`: `29280.1`
* `total_exception_count`: `200`
* `billing_exception_rate_pct`: `5.28`

### 2.3 Natural Language AI Inquiry
```bash
curl -s -X POST http://localhost:8000/api/v1/analytics/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What was our total net recognized revenue?", "environment": "dev"}' | jq .
```

---

## 3. Operational Troubleshooting

| Symptom | Cause | Solution |
| :--- | :--- | :--- |
| **API returns 500 on database probe** | PostgreSQL container not reachable | Verify `docker compose ps` and check `POSTGRES_HOST` / `POSTGRES_PORT` in `.env`. |
| **`analytics_reader` permission denied** | Grants missing on new dbt relation | Re-run `packages/data_platform/src/data_platform/sql/provision_analytics_reader.sql`. |
| **Streamlit shows disconnected database** | Reader credentials mismatch | Ensure `POSTGRES_READER_PASSWORD` matches database user configuration. |
| **Query execution timeout (5000ms)** | Complex query exceeding limit | Optimize query with date/partition filters or inspect PostgreSQL lock contention. |
