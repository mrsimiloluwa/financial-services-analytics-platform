"""Data classification rules and governance sensitivity assignment engine."""

from __future__ import annotations

import logging
from typing import Any

from data_platform.metadata.schemas import (
    ColumnMetadata,
    DataClassification,
    ModelMetadata,
    SourceMetadata,
)

logger = logging.getLogger("data_platform.metadata.classifications")

# Field naming patterns indicating confidential customer or account data
CONFIDENTIAL_PATTERNS = {
    "customer_id",
    "customer_name",
    "legal_entity_id",
    "account_id",
    "account_number",
    "transaction_id",
    "counterparty_account_id",
    "transaction_amount",
    "opening_balance",
    "authorized_limit",
    "linked_ledger_entry_id",
}

RESTRICTED_PATTERNS = {
    "password",
    "secret",
    "api_key",
    "token",
    "private_key",
    "credentials",
}


class ClassificationEngine:
    """Applies enterprise classification policies, inheritance, and pattern overrides."""

    def __init__(self) -> None:
        pass

    def classify_models(self, models: dict[str, ModelMetadata]) -> None:
        """Classify a dictionary of ModelMetadata objects."""
        for model in models.values():
            self.classify_model(model)

    def classify_sources(self, sources: dict[str, SourceMetadata]) -> None:
        """Classify a dictionary of SourceMetadata objects."""
        for source in sources.values():
            self.classify_source(source)

    def classify_model(self, model: ModelMetadata, raw_node: dict[str, Any] | None = None) -> None:
        """Assign model-level sensitivity and cascade to child columns."""
        # 1. Check for explicit YAML override in meta
        meta = (raw_node or {}).get("meta", {})
        explicit_class = meta.get("classification")

        if explicit_class:
            try:
                model.classification = DataClassification(str(explicit_class).upper())
            except ValueError:
                logger.warning(
                    "Invalid classification '%s' on model '%s'. Defaulting to INTERNAL.",
                    explicit_class,
                    model.name,
                )
                model.classification = DataClassification.INTERNAL
        else:
            # Default model classification
            model.classification = DataClassification.INTERNAL

        # 2. Classify individual columns
        for _col_name, column in model.columns.items():
            self.classify_column(column, parent_classification=model.classification)

    def classify_source(
        self, source: SourceMetadata, raw_source: dict[str, Any] | None = None
    ) -> None:
        """Raw source tables are confidential by default in banking environments."""
        meta = (raw_source or {}).get("meta", {})
        explicit_class = meta.get("classification")

        if explicit_class:
            try:
                source.classification = DataClassification(str(explicit_class).upper())
            except ValueError:
                source.classification = DataClassification.CONFIDENTIAL
        else:
            source.classification = DataClassification.CONFIDENTIAL

        for _col_name, column in source.columns.items():
            self.classify_column(column, parent_classification=source.classification)

    def classify_column(
        self,
        column: ColumnMetadata,
        parent_classification: DataClassification = DataClassification.INTERNAL,
    ) -> None:
        """Classify column based on name heuristics, inheritance, and sensitivity tiers."""
        lower_name = column.name.lower()

        # Check restricted keywords
        if any(pat in lower_name for pat in RESTRICTED_PATTERNS):
            column.classification = DataClassification.RESTRICTED
            return

        # Check confidential customer / account patterns
        if lower_name in CONFIDENTIAL_PATTERNS or any(
            lower_name.endswith(f"_{p}") for p in CONFIDENTIAL_PATTERNS
        ):
            column.classification = DataClassification.CONFIDENTIAL
            return

        # Otherwise inherit from parent model/source
        column.classification = parent_classification

    @staticmethod
    def redact_confidential_metadata(metadata_dict: dict[str, Any]) -> dict[str, Any]:
        """Strip raw values or mask confidential attributes from user-facing query responses."""
        sanitized = metadata_dict.copy()
        # Ensure credentials/secrets are never present
        for key in list(sanitized.keys()):
            if any(p in key.lower() for p in RESTRICTED_PATTERNS):
                sanitized[key] = "[REDACTED_SECRET]"
        return sanitized
