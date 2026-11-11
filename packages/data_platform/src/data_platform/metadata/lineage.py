"""Lineage engine for model-level and column-level dependency graphs."""

from __future__ import annotations

import logging
import re
from collections import deque

import sqlglot
from sqlglot import exp

from data_platform.metadata.schemas import LineageEdge

logger = logging.getLogger(__name__)


class LineageEngine:
    """Computes, traverses, and visualizes model-level and column-level data lineage."""

    def __init__(
        self,
        parent_map: dict[str, list[str]] | None = None,
        child_map: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the lineage engine with optional parent/child adjacency maps."""
        self.parent_map: dict[str, list[str]] = parent_map or {}
        self.child_map: dict[str, list[str]] = child_map or {}

    def build_model_edges(self) -> list[LineageEdge]:
        """Generate directed LineageEdge records for all parent-child model dependencies."""
        edges: list[LineageEdge] = []
        for child_id, parents in self.parent_map.items():
            for parent_id in parents:
                if parent_id.startswith("source."):
                    edge_type = "SOURCE_TO_MODEL"
                elif parent_id.startswith("model."):
                    edge_type = "MODEL_TO_MODEL"
                else:
                    edge_type = "DEPENDENCY"

                edges.append(
                    LineageEdge(
                        source_id=parent_id,
                        target_id=child_id,
                        edge_type=edge_type,
                        details={"parent": parent_id, "child": child_id},
                    )
                )
        return edges

    def get_upstream_nodes(self, node_id: str, depth: int | None = None) -> set[str]:
        """Traverse upstream dependencies from node_id up to the specified depth."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if depth is not None and current_depth >= depth:
                continue

            for parent in self.parent_map.get(current, []):
                if parent not in visited:
                    visited.add(parent)
                    queue.append((parent, current_depth + 1))

        return visited

    def get_downstream_nodes(self, node_id: str, depth: int | None = None) -> set[str]:
        """Traverse downstream dependencies from node_id down to the specified depth."""
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if depth is not None and current_depth >= depth:
                continue

            for child in self.child_map.get(current, []):
                if child not in visited:
                    visited.add(child)
                    queue.append((child, current_depth + 1))

        return visited

    def trace_mart_to_sources(self, mart_model_id: str) -> list[str]:
        """Trace all raw source dependencies upstream of a dimensional mart."""
        upstream = self.get_upstream_nodes(mart_model_id)
        return sorted([node for node in upstream if node.startswith("source.")])

    def trace_source_to_marts(self, source_id: str) -> list[str]:
        """Trace all business-facing dimensional marts downstream of a raw source."""
        downstream = self.get_downstream_nodes(source_id)
        return sorted(
            [node for node in downstream if node.startswith("model.") and ".marts." in node]
        )

    def generate_mermaid_diagram(
        self,
        root_node_id: str | None = None,
        direction: str = "LR",
        depth: int | None = None,
    ) -> str:
        """Generate a Mermaid diagram representing data lineage.

        If root_node_id is specified, generates lineage focused around that node.
        Otherwise, generates the entire model dependency graph.
        """
        lines: list[str] = [f"graph {direction}"]

        if root_node_id:
            relevant_nodes = {root_node_id}
            relevant_nodes.update(self.get_upstream_nodes(root_node_id, depth=depth))
            relevant_nodes.update(self.get_downstream_nodes(root_node_id, depth=depth))
        else:
            relevant_nodes = set(self.parent_map.keys())
            for parents in self.parent_map.values():
                relevant_nodes.update(parents)

        # Style groupings
        for node in sorted(relevant_nodes):
            clean_id = node.replace(".", "_").replace("-", "_")
            label = node.split(".")[-1]
            if node.startswith("source."):
                parts = node.split(".")
                source_name = parts[2] if len(parts) > 2 else "raw"
                table_name = parts[-1]
                lines.append(f'    {clean_id}[("{source_name}.{table_name}")]')
            elif ".marts." in node:
                lines.append(f"    {clean_id}[/{label}/]")
            elif ".intermediate." in node:
                lines.append(f"    {clean_id}({label})")
            elif ".staging." in node:
                lines.append(f"    {clean_id}[{label}]")
            else:
                lines.append(f"    {clean_id}[{label}]")

        # Edges
        for child_id, parents in sorted(self.parent_map.items()):
            if child_id not in relevant_nodes:
                continue
            child_clean = child_id.replace(".", "_").replace("-", "_")
            for parent_id in sorted(parents):
                if parent_id in relevant_nodes:
                    parent_clean = parent_id.replace(".", "_").replace("-", "_")
                    lines.append(f"    {parent_clean} --> {child_clean}")

        return "\n".join(lines)


class ColumnLineageAnalyzer:
    """Conservative column-level lineage analyzer using SQLGlot AST analysis."""

    def __init__(self, dialect: str = "postgres") -> None:
        """Initialize analyzer with SQL dialect."""
        self.dialect = dialect

    def analyze_sql(
        self,
        sql: str,
        upstream_columns_by_alias: dict[str, list[str]] | None = None,
    ) -> dict[str, list[str]]:
        """Extract conservative column-to-column lineage from SQL query text.

        Returns a dictionary mapping target output column names to lists of upstream
        column names. If an expression is complex or ambiguous, maps to AMBIGUOUS_COMPLEX_EXPRESSION.
        """
        result: dict[str, list[str]] = {}
        # Pre-clean Jinja macros and blocks if uncompiled dbt SQL
        cleaned_sql = re.sub(r"\{%.*?%\}", "", sql, flags=re.DOTALL)
        cleaned_sql = re.sub(
            r"\{\{\s*(?:ref|source)\s*\([^)]+\)\s*\}\}", "source_table", cleaned_sql
        )
        cleaned_sql = re.sub(r"\{\{.*?\}\}", "NULL", cleaned_sql, flags=re.DOTALL)

        try:
            expression = sqlglot.parse_one(cleaned_sql, read=self.dialect)
        except Exception as exc:
            logger.warning("Failed to parse SQL with sqlglot: %s", exc)
            return {"*": ["UNPARSEABLE_SQL"]}

        # Find top-level SELECT
        select_node = expression
        if not isinstance(expression, exp.Select):
            selects = expression.find_all(exp.Select)
            select_node = next(selects, None)

        if not select_node:
            return {}

        for select_expr in select_node.expressions:
            target_col = select_expr.alias_or_name
            if not target_col:
                continue

            # Check direct column reference
            if isinstance(select_expr, exp.Column):
                col_name = select_expr.name
                result[target_col] = [col_name]
            elif isinstance(select_expr, exp.Alias):
                this = select_expr.this
                if isinstance(this, exp.Column):
                    result[target_col] = [this.name]
                elif isinstance(this, exp.Cast) and isinstance(this.this, exp.Column):
                    result[target_col] = [this.this.name]
                else:
                    # Find any direct Column identifiers in expression
                    inner_cols = [c.name for c in this.find_all(exp.Column) if c.name]
                    if inner_cols:
                        # Direct extracted column references
                        result[target_col] = sorted(set(inner_cols))
                    else:
                        result[target_col] = ["AMBIGUOUS_COMPLEX_EXPRESSION"]
            else:
                inner_cols = [c.name for c in select_expr.find_all(exp.Column) if c.name]
                if inner_cols:
                    result[target_col] = sorted(set(inner_cols))
                else:
                    result[target_col] = ["AMBIGUOUS_COMPLEX_EXPRESSION"]

        return result
