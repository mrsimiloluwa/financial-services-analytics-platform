"""Automated dbt artifact publisher and versioned storage manager."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from data_platform.metadata.schemas import ArtifactRun

logger = logging.getLogger("data_platform.metadata.artifacts")

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_DBT_TARGET_DIR = DEFAULT_REPO_ROOT / "packages/data_platform/dbt_analytics/target"
DEFAULT_ARTIFACTS_DIR = DEFAULT_REPO_ROOT / "artifacts/dbt"


class DbtArtifactManager:
    """Manages validation, versioned persistence, and latest-state promotion for dbt JSON artifacts."""

    REQUIRED_ARTIFACTS = ("manifest.json", "catalog.json", "run_results.json")

    def __init__(
        self,
        dbt_target_dir: Path = DEFAULT_DBT_TARGET_DIR,
        artifacts_root: Path = DEFAULT_ARTIFACTS_DIR,
    ) -> None:
        self.dbt_target_dir = dbt_target_dir
        self.artifacts_root = artifacts_root

    def validate_artifacts(self, target_dir: Path | None = None) -> dict[str, dict]:
        """Verify that required dbt artifacts exist, are valid JSON, and contain expected top-level keys."""
        source_dir = target_dir or self.dbt_target_dir
        validated: dict[str, dict] = {}

        for filename in self.REQUIRED_ARTIFACTS:
            path = source_dir / filename
            if not path.exists():
                raise FileNotFoundError(
                    f"Required dbt artifact '{filename}' not found at {path}. "
                    "Ensure 'dbt build' and 'dbt docs generate' have executed successfully."
                )

            try:
                content = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON in artifact '{filename}': {exc}") from exc

            # Verify presence of essential dbt artifact structures
            if "metadata" not in content:
                raise ValueError(
                    f"Artifact '{filename}' is missing required top-level 'metadata' block."
                )

            validated[filename] = content

        # Additional specific structure checks
        if "nodes" not in validated["manifest.json"]:
            raise ValueError("manifest.json missing 'nodes' dictionary.")
        if "nodes" not in validated["catalog.json"]:
            raise ValueError("catalog.json missing 'nodes' dictionary.")
        if "results" not in validated["run_results.json"]:
            raise ValueError("run_results.json missing 'results' list.")

        return validated

    def publish_artifacts(
        self,
        environment: str = "dev",
        run_id: str | None = None,
        build_status: str = "SUCCESS",
    ) -> ArtifactRun:
        """Store versioned snapshot of dbt artifacts and atomically promote to 'latest' if successful."""
        artifacts = self.validate_artifacts()
        manifest = artifacts["manifest.json"]

        # Extract manifest metadata
        meta = manifest.get("metadata", {})
        dbt_version = meta.get("dbt_version", "unknown")
        adapter_type = meta.get("adapter_type", "postgres")
        target_name = meta.get("target_name", environment)

        # Count models, sources, and tests
        nodes = manifest.get("nodes", {})
        sources = manifest.get("sources", {})
        total_models = sum(1 for k in nodes if k.startswith("model."))
        total_tests = sum(1 for k in nodes if k.startswith("test."))
        total_sources = len(sources)

        # Determine target database/schema
        first_model = next((v for k, v in nodes.items() if k.startswith("model.")), {})
        database_name = first_model.get("database", "analytics_platform")
        schema_name = first_model.get("schema", "analytics")

        active_run_id = run_id or f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        env_dir = self.artifacts_root / environment
        snapshot_dir = env_dir / active_run_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        # Copy JSON artifacts into versioned snapshot directory
        for filename in self.REQUIRED_ARTIFACTS:
            src_file = self.dbt_target_dir / filename
            dst_file = snapshot_dir / filename
            shutil.copy2(src_file, dst_file)

        artifact_run = ArtifactRun(
            run_id=active_run_id,
            environment=environment,
            created_at=datetime.now(UTC),
            dbt_version=dbt_version,
            adapter_type=adapter_type,
            target_name=target_name,
            database_name=database_name,
            schema_name=schema_name,
            total_models=total_models,
            total_sources=total_sources,
            total_tests=total_tests,
            build_status=build_status,
            artifact_path=str(snapshot_dir),
            is_latest=(build_status == "SUCCESS"),
        )

        # Save run manifest
        manifest_file = snapshot_dir / "artifact_manifest.json"
        manifest_file.write_text(artifact_run.model_dump_json(indent=2), encoding="utf-8")

        # Promote to 'latest' only on successful builds
        if build_status == "SUCCESS":
            latest_dir = env_dir / "latest"
            if latest_dir.exists():
                if latest_dir.is_symlink():
                    latest_dir.unlink()
                else:
                    shutil.rmtree(latest_dir)

            # Copy to latest directory for cross-platform reliability
            shutil.copytree(snapshot_dir, latest_dir)
            logger.info("Promoted snapshot '%s' to %s", active_run_id, latest_dir)

        return artifact_run

    def get_latest_dir(self, environment: str = "dev") -> Path:
        """Retrieve path to latest published artifact directory for given environment."""
        latest_dir = self.artifacts_root / environment / "latest"
        if not latest_dir.exists():
            raise FileNotFoundError(
                f"No published artifacts found for environment '{environment}' at {latest_dir}."
            )
        return latest_dir

    def load_manifest(self) -> dict:
        """Load and parse manifest.json from dbt target directory."""
        path = self.dbt_target_dir / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"manifest.json not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def load_catalog(self) -> dict:
        """Load and parse catalog.json from dbt target directory."""
        path = self.dbt_target_dir / "catalog.json"
        if not path.exists():
            raise FileNotFoundError(f"catalog.json not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def load_run_results(self) -> dict:
        """Load and parse run_results.json from dbt target directory."""
        path = self.dbt_target_dir / "run_results.json"
        if not path.exists():
            raise FileNotFoundError(f"run_results.json not found at {path}")
        return json.loads(path.read_text(encoding="utf-8"))
