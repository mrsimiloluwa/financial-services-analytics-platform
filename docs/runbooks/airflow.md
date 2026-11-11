# Runbook: Apache Airflow Pipeline Operations

This operational runbook provides step-by-step procedures for starting, managing, monitoring, troubleshooting, and recovering Apache Airflow within the Financial Services Analytics & AI Platform.

---

## 1. Prerequisites

Before starting Airflow services, ensure:
- Docker Desktop or Docker Engine is running.
- Port `5432` (PostgreSQL) and Port `8080` (Airflow Web UI) are available on `127.0.0.1`.
- Project environment variables are set (copy `.env.example` to `.env` if not present).

---

## 2. Service Startup & Initialization

### Step 1: Start PostgreSQL Database Container
```bash
docker compose up -d postgres
```
Verify that PostgreSQL is healthy:
```bash
docker compose ps postgres
```

### Step 2: Initialize Airflow Metadata Database
Run database migrations and seed the administrator user (`admin` / `admin`):
```bash
docker compose up airflow-init
```
Expected output:
```text
Database migrating done!
User "admin" created with role "Admin"
analytics_platform_airflow_init exited with code 0
```

### Step 3: Launch Airflow Webserver and Scheduler
```bash
docker compose up -d airflow-webserver airflow-scheduler
```

---

## 3. Operational Verification

### Check Container Status
```bash
docker compose ps
```
All services should report `Up` and `healthy`:
```text
NAME                                   IMAGE                   COMMAND                  SERVICE             STATUS
analytics_platform_airflow_scheduler   custom-airflow:2.10.3   "/usr/bin/dumb-init …"   airflow-scheduler   Up (healthy)
analytics_platform_airflow_webserver   custom-airflow:2.10.3   "/usr/bin/dumb-init …"   airflow-webserver   Up (healthy)
analytics_platform_postgres            postgres:16-alpine      "docker-entrypoint.s…"   postgres            Up (healthy)
```

### Health Check Endpoint
Query the Airflow REST health endpoint from the developer terminal:
```bash
curl -s http://127.0.0.1:8080/health
```
Expected response:
```json
{
  "metadatabase": {"status": "healthy"},
  "scheduler": {"status": "healthy"}
}
```

### Accessing the Web UI
Open your browser to:
- **URL:** [http://127.0.0.1:8080](http://127.0.0.1:8080)
- **Username:** `admin`
- **Password:** `admin`

---

## 4. Triggering Pipeline Executions

### Trigger Development Pipeline (`financial_analytics_dev_pipeline`)
```bash
docker compose exec airflow-webserver airflow dags trigger financial_analytics_dev_pipeline
```

### Trigger Test Pipeline (`financial_analytics_test_pipeline`)
```bash
docker compose exec airflow-webserver airflow dags trigger financial_analytics_test_pipeline
```

---

## 5. Monitoring & Inspecting Executions

### List DAG Runs
```bash
docker compose exec airflow-webserver airflow dags list-runs -d financial_analytics_dev_pipeline
```

### View Task States for a Run
```bash
docker compose exec airflow-webserver airflow tasks states-for-dag-run financial_analytics_dev_pipeline <run_id>
```

### Inspect Task Logs on Host
Task logs are written directly to the host filesystem:
```bash
# View recent execution logs for a task
cat airflow/logs/dag_id=financial_analytics_dev_pipeline/run_id=<run_id>/task_id=dbt_build_analytics/attempt=1.log
```

---

## 6. Common Troubleshooting Scenarios

### 1. Port 8080 Conflict
**Symptom:** `Error starting userland proxy: listen tcp4 127.0.0.1:8080: bind: address already in use`  
**Resolution:** Identify process occupying port 8080 and terminate it:
```bash
lsof -i :8080
# Or override AIRFLOW_PORT in .env (e.g., AIRFLOW_PORT=8081)
```

### 2. Database Connection Error (`could not translate host name "postgres"`)
**Symptom:** Tasks fail with connection failure to `postgres:5432`.  
**Resolution:** Ensure Airflow containers are attached to the same Docker network as `analytics_platform_postgres`. Restart the network:
```bash
docker compose down
docker compose up -d
```

### 3. Task Failed with `up_for_retry`
**Symptom:** Task enters `up_for_retry` state after failure.  
**Resolution:** Clear the task to force immediate re-execution without waiting for backoff timer:
```bash
docker compose exec airflow-webserver airflow tasks clear financial_analytics_dev_pipeline -t <task_id> -y
```

---

## 7. Service Shutdown & Cleanup

### Stop Airflow Services (Preserving State)
```bash
docker compose stop airflow-webserver airflow-scheduler
```

### Tear Down Complete Stack (Preserving Database Volume)
```bash
docker compose down
```

### Full Reset (WARNING: Destroys Database Volume)
```bash
docker compose down -v
```
