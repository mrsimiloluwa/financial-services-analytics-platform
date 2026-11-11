"""Command-line interface for metadata publishing, extraction, and inspection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from data_platform.metadata.extractor import MetadataExtractor
from data_platform.metadata.service import MetadataService


def main() -> int:
    """CLI entrypoint for metadata catalog operations."""
    parser = argparse.ArgumentParser(description="Governed Metadata Catalog CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # publish-and-load
    pub_parser = subparsers.add_parser(
        "publish-and-load", help="Publish dbt artifacts and persist metadata catalog to PostgreSQL"
    )
    pub_parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("packages/data_platform/dbt_analytics/target"),
        help="Path to dbt compilation target directory",
    )
    pub_parser.add_argument(
        "--environment",
        type=str,
        default="dev",
        help="Target environment (dev, test, prod)",
    )

    # inspect
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect loaded metadata catalog summary"
    )
    inspect_parser.add_argument("--model", type=str, help="Inspect specific model")

    # ai-context
    ai_parser = subparsers.add_parser(
        "ai-context", help="Generate AI QueryContext JSON for a governed model"
    )
    ai_parser.add_argument(
        "--model", type=str, required=True, help="Model name (e.g. fct_transactions)"
    )

    # lineage-mermaid
    lineage_parser = subparsers.add_parser(
        "lineage-mermaid", help="Generate Mermaid lineage diagram"
    )
    lineage_parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("packages/data_platform/dbt_analytics/target"),
    )
    lineage_parser.add_argument("--model", type=str, help="Root model name")

    args = parser.parse_args()

    if args.command == "publish-and-load":
        service = MetadataService()
        run = service.publish_and_load(
            target_dir=args.target_dir,
            environment=args.environment,
        )
        print(f"Successfully published and loaded metadata run: {run.run_id}")
        print(f"  Environment: {run.environment}")
        print(f"  Models: {run.total_models}")
        print(f"  Sources: {run.total_sources}")
        print(f"  Tests: {run.total_tests}")
        print(f"  Artifact Path: {run.artifact_path}")
        return 0

    elif args.command == "inspect":
        service = MetadataService()
        if args.model:
            model = service.get_model(args.model)
            if not model:
                print(f"Model '{args.model}' not found in catalog.")
                return 1
            print(f"Model: {model.name} (Layer: {model.layer}, Queryable: {model.is_queryable})")
            print(f"Classification: {model.classification.value}")
            print(f"Description: {model.description}")
            print(f"Columns ({len(model.columns)}):")
            for cname, col in model.columns.items():
                print(
                    f"  - {cname} ({col.data_type}): {col.classification.value} | {col.description}"
                )
        else:
            models = service.list_queryable_models()
            metrics = service.list_metrics()
            print(f"Governed Queryable Marts ({len(models)}):")
            for m in models:
                print(f"  - {m.name} ({m.layer}) - {m.classification.value}")
            print(f"\nGoverned Financial Metrics ({len(metrics)}):")
            for met in metrics:
                print(f"  - {met.metric_id} [{met.aggregation_behavior}]: {met.formula}")
        return 0

    elif args.command == "ai-context":
        service = MetadataService()
        ctx = service.build_ai_query_context(args.model)
        print(ctx.model_dump_json(indent=2))
        return 0

    elif args.command == "lineage-mermaid":
        extractor = MetadataExtractor(target_dir=args.target_dir)
        snapshot = extractor.extract()
        if snapshot.lineage_engine:
            diagram = snapshot.lineage_engine.generate_mermaid_diagram(root_node_id=args.model)
            print(diagram)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
