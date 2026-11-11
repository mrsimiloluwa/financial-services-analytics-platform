"""Deterministic mock LLM provider for CI testing and verifiable evaluation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, TypeVar

from ai_services.providers.base import BaseLLMProvider
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class DeterministicMockLLMProvider(BaseLLMProvider):
    """Deterministic, zero-latency provider that outputs verified financial logic."""

    @staticmethod
    def _extract_user_question(prompt: str) -> str:
        """Extract user question line from multi-line prompt to isolate intent from context."""
        lower = prompt.lower()
        for line in prompt.splitlines():
            line_clean = line.strip().lower()
            if line_clean.startswith("user question:"):
                return line_clean.replace("user question:", "").strip()
        return lower

    @staticmethod
    def _extract_query_rows(prompt: str) -> list[dict[str, Any]]:
        """Parse structured query result rows from prompt payload."""
        match = re.search(r"Query Results \(Row Count: \d+\):\s*(\[.*?\])", prompt, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                return []
        return []

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Return deterministic text based on pattern matching in prompt."""
        user_q = self._extract_user_question(prompt)
        lower = prompt.lower()

        # Prompt Injection & Security Attack Detection
        if any(
            term in user_q
            for term in [
                "ignore previous",
                "drop table",
                "raw.",
                "stg_",
                "information_schema",
                "delete from",
                "truncate",
            ]
        ):
            return "I cannot fulfill this request. I am restricted exclusively to querying certified dimensional analytics marts."

        # Answer Synthesis Requests (check before SQL generation since prompt contains executed SELECT)
        if (
            "synthesize" in lower
            or "financial explanation" in lower
            or "query results" in lower
            or "explain these numbers" in lower
        ):
            return self._generate_mock_answer(prompt, user_q)

        # SQL Generation Requests
        if (
            "generate sql" in lower
            or "select" in lower
            or "query context" in lower
            or "primary model" in lower
            or "analytical query" in lower
            or "postgresql 16" in lower
        ):
            return self._generate_mock_sql(user_q)

        return "This financial inquiry was analyzed against certified dimensional warehouse models."

    def generate_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        """Synthesize structured mock outputs conforming to target Pydantic models."""
        from ai_services.schemas import MetricResolution, QuestionUnderstanding

        user_q = self._extract_user_question(prompt)

        if response_model == QuestionUnderstanding:
            if any(
                term in user_q
                for term in [
                    "ignore previous",
                    "system prompt",
                    "drop table",
                    "raw.",
                    "delete from",
                    "truncate",
                    "alter table",
                    "metadata.",
                    "password",
                    "secret",
                    "override",
                    "information_schema",
                ]
            ):
                return response_model(
                    intent="MALICIOUS_PROMPT_INJECTION",
                    is_out_of_scope=True,
                    rejection_reason="Prompt injection or security boundary violation attempt detected.",
                )  # type: ignore[return-value]

            if any(
                term in user_q
                for term in [
                    "weather",
                    "sports",
                    "recipe",
                    "cake",
                    "bake",
                    "write a poem",
                    "chess",
                    "football",
                    "world cup",
                    "python script",
                ]
            ):
                return response_model(
                    intent="GENERAL_NON_FINANCIAL",
                    is_out_of_scope=True,
                    rejection_reason="Inquiry is outside the scope of commercial banking and financial analytics.",
                )  # type: ignore[return-value]

            # Questions the deterministic demo engine has no routing for must not silently fall
            # through to the revenue default, which would answer a different question.
            if not self._count_target(user_q) and not any(
                term in user_q for term in self._SUPPORTED_TOPIC_TERMS
            ):
                return response_model(
                    intent="UNSUPPORTED_BY_DEMO_ENGINE",
                    is_out_of_scope=True,
                    rejection_reason=(
                        "The demo engine does not recognise this question. Try asking about "
                        "revenue, fees, collections, arrears, reversals, customers, segments, "
                        "or transaction volume — or how many customers, accounts or "
                        "transactions there are."
                    ),
                )  # type: ignore[return-value]

            # Financial question decomposition
            intent = "FINANCIAL_METRIC_QUERY"
            period = None
            if "last month" in user_q or "november" in user_q:
                period = "2026-11"
            elif "q4" in user_q:
                period = "2026-Q4"

            return response_model(
                intent=intent,
                entities={"query": user_q},
                time_period=period,
                is_out_of_scope=False,
            )  # type: ignore[return-value]

        if response_model == MetricResolution:
            # 0. Entity counts (descriptive, not a governed financial metric)
            count_target = self._count_target(user_q)
            if count_target:
                model, alias = count_target
                entity = alias.replace("total_", "")
                return response_model(
                    metric_id=f"{entity}_count",
                    metric_name=f"Number of {entity.capitalize()} (descriptive row count)",
                    source_model=model,
                    formula="COUNT(*)",
                    confidence=0.9,
                )  # type: ignore[return-value]

            # 1. Reversals
            if "revers" in user_q or "chargeback" in user_q or "cancell" in user_q:
                return response_model(
                    metric_id="reversal_rate",
                    metric_name="Transaction Reversal Rate",
                    source_model="fct_transactions",
                    formula="COUNT(*) FILTER (WHERE transaction_status = 'REVERSED')::float / NULLIF(COUNT(*), 0)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            # 2. Exceptions & Arrears
            if (
                "exception" in user_q
                or "outstanding" in user_q
                or "arrears" in user_q
                or "past due" in user_q
            ):
                return response_model(
                    metric_id="billing_exception_rate",
                    metric_name="Billing Exception & Arrears Rate",
                    source_model="fct_fee_assessments",
                    formula="COUNT(*) FILTER (WHERE outstanding_amount > 0)::float / NULLIF(COUNT(*), 0)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            # 3. Fee Collection & Waivers
            if "waiv" in user_q:
                return response_model(
                    metric_id="waived_fees",
                    metric_name="Waived Fees",
                    source_model="fct_fee_assessments",
                    formula="SUM(waived_amount_eur)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            if "collection rate" in user_q or "collected fees" in user_q or "realiz" in user_q:
                return response_model(
                    metric_id="fee_collection_rate",
                    metric_name="Fee Collection Realization Rate",
                    source_model="fct_fee_assessments",
                    formula="SUM(collected_amount_eur) / NULLIF(SUM(net_collectible_amount_eur), 0)",
                    confidence=0.97,
                )  # type: ignore[return-value]

            if "contractual" in user_q or "assess" in user_q:
                return response_model(
                    metric_id="assessed_fees",
                    metric_name="Gross Assessed Fees",
                    source_model="fct_fee_assessments",
                    formula="SUM(gross_assessed_amount)",
                    confidence=0.96,
                )  # type: ignore[return-value]

            # 4. Customer Profitability & Segments
            if "segment" in user_q or "profitab" in user_q or "contribution" in user_q:
                return response_model(
                    metric_id="net_customer_profitability",
                    metric_name="Net Customer Fee Contribution Margin",
                    source_model="fct_customer_revenue",
                    formula="SUM(net_recognized_revenue_eur)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            # 5. Volume & Transaction
            if "volume" in user_q:
                return response_model(
                    metric_id="gross_transaction_volume",
                    metric_name="Gross Transaction Volume",
                    source_model="fct_transactions",
                    formula="SUM(transaction_amount_eur)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            # 6. Take rate
            if "take rate" in user_q:
                return response_model(
                    metric_id="effective_take_rate",
                    metric_name="Effective Fee Realization Rate",
                    source_model="fct_customer_revenue",
                    formula="SUM(net_recognized_revenue_eur) / NULLIF(SUM(gross_assessed_fee_amount_eur), 0)",
                    confidence=0.95,
                )  # type: ignore[return-value]

            # 7. Revenue (default)
            return response_model(
                metric_id="recognized_revenue",
                metric_name="Recognized Revenue",
                source_model="fct_customer_revenue",
                formula="SUM(net_recognized_revenue_eur)",
                confidence=0.98,
            )  # type: ignore[return-value]

        # Generic structured fallback
        return response_model.model_validate({})

    # Dimension/fact row-count questions ("how many customers?"). These are descriptive counts of
    # warehouse entities, not governed financial metrics, so they never touch monetary formulas.
    _COUNT_TARGETS: tuple[tuple[tuple[str, ...], str, str], ...] = (
        (("customer", "client"), "dim_customers", "total_customers"),
        (("account",), "dim_accounts", "total_accounts"),
        (("transaction",), "fct_transactions", "total_transactions"),
    )
    _COUNT_TRIGGERS = ("how many", "number of", "count of", "total number")
    _SUPPORTED_TOPIC_TERMS = (
        "revenue",
        "income",
        "fee",
        "collect",
        "realiz",
        "waiv",
        "arrear",
        "outstanding",
        "exception",
        "past due",
        "revers",
        "chargeback",
        "cancell",
        "segment",
        "profit",
        "contribution",
        "customer",
        "client",
        "volume",
        "take rate",
        "assess",
        "contractual",
        "transaction",
        "account",
        "financ",
        "figure",
        "overview",
        "summary",
        "kpi",
        "performance",
        "metric",
        "total",
        "bank",
        "money",
        "profit",
        "earn",
        "report",
    )
    _COUNT_EXCLUSIONS = (
        "arrear",
        "outstanding",
        "exception",
        "past due",
        "revers",
        "waiv",
        "revenue",
        "fee",
    )

    @classmethod
    def _count_target(cls, user_q: str) -> tuple[str, str] | None:
        """Return (source_model, count_alias) when the question asks for an entity count."""
        if not any(t in user_q for t in cls._COUNT_TRIGGERS):
            return None
        if any(x in user_q for x in cls._COUNT_EXCLUSIONS):
            return None
        for keywords, model, alias in cls._COUNT_TARGETS:
            if any(k in user_q for k in keywords):
                return model, alias
        return None

    def _generate_mock_sql(self, user_q: str) -> str:
        """Generate verified, syntax-clean SQL targeting approved analytics models."""
        count_target = self._count_target(user_q)
        if count_target:
            model, alias = count_target
            return f"SELECT COUNT(*) AS {alias} FROM analytics.{model} LIMIT 1000;"

        if "segment" in user_q or "profitab" in user_q:
            return (
                "SELECT c.customer_segment, "
                "SUM(r.net_recognized_revenue_eur) AS recognized_revenue_eur "
                "FROM analytics.fct_customer_revenue r "
                "JOIN analytics.dim_customers c ON r.customer_id = c.customer_id "
                "GROUP BY c.customer_segment "
                "ORDER BY recognized_revenue_eur DESC LIMIT 1000;"
            )

        if "top customer" in user_q or "most revenue" in user_q or "which customer" in user_q:
            return (
                "SELECT c.customer_name, c.customer_segment, "
                "SUM(r.net_recognized_revenue_eur) AS recognized_revenue_eur "
                "FROM analytics.fct_customer_revenue r "
                "JOIN analytics.dim_customers c ON r.customer_id = c.customer_id "
                "GROUP BY c.customer_name, c.customer_segment "
                "ORDER BY recognized_revenue_eur DESC LIMIT 10;"
            )

        if "collection rate" in user_q or "collected fees" in user_q or "realiz" in user_q:
            return (
                "SELECT "
                "ROUND((SUM(collected_amount_eur) / NULLIF(SUM(net_collectible_amount_eur), 0) * 100)::numeric, 2) AS fee_collection_rate_pct, "
                "SUM(collected_amount_eur) AS total_collected_eur, "
                "SUM(net_collectible_amount_eur) AS total_collectible_eur "
                "FROM analytics.fct_fee_assessments LIMIT 1000;"
            )

        if "assess" in user_q:
            return (
                "SELECT "
                "currency, "
                "SUM(gross_assessed_amount) AS total_assessed_amount, "
                "COUNT(*) AS assessment_count "
                "FROM analytics.fct_fee_assessments "
                "GROUP BY currency LIMIT 1000;"
            )

        if "waiv" in user_q:
            return (
                "SELECT "
                "fee_type, "
                "SUM(waived_amount_eur) AS total_waived_eur, "
                "COUNT(*) AS waived_count "
                "FROM analytics.fct_fee_assessments "
                "WHERE waived_amount_eur > 0 "
                "GROUP BY fee_type LIMIT 1000;"
            )

        # Arrears breakdown by customer / account
        if "by customer" in user_q or "which account" in user_q or "past due fee" in user_q:
            return (
                "SELECT "
                "customer_name, "
                "customer_segment, "
                "fee_type, "
                "currency, "
                "SUM(outstanding_amount_eur) AS outstanding_amount_eur, "
                "COUNT(*) AS assessment_count "
                "FROM analytics.fct_fee_assessments "
                "WHERE outstanding_amount > 0 "
                "GROUP BY customer_name, customer_segment, fee_type, currency "
                "ORDER BY outstanding_amount_eur DESC LIMIT 10;"
            )

        # Portfolio-level exception summary
        if "outstanding" in user_q or "exception" in user_q or "arrears" in user_q:
            return (
                "SELECT "
                "COUNT(*) FILTER (WHERE outstanding_amount > 0) AS total_exception_count, "
                "COUNT(DISTINCT CASE WHEN outstanding_amount > 0 THEN customer_id END) AS impacted_customers_count, "
                "SUM(CASE WHEN outstanding_amount > 0 THEN outstanding_amount_eur ELSE 0 END) AS total_arrears_eur, "
                "COUNT(*) AS total_assessment_count, "
                "ROUND((COUNT(*) FILTER (WHERE outstanding_amount > 0)::float / NULLIF(COUNT(*), 0) * 100)::numeric, 2) AS billing_exception_rate_pct "
                "FROM analytics.fct_fee_assessments LIMIT 1000;"
            )

        if "revers" in user_q or "chargeback" in user_q or "cancell" in user_q:
            return (
                "SELECT "
                "ROUND((COUNT(*) FILTER (WHERE transaction_status = 'REVERSED')::float / NULLIF(COUNT(*), 0) * 100)::numeric, 2) AS reversal_rate_pct, "
                "COUNT(*) FILTER (WHERE transaction_status = 'REVERSED') AS reversed_count, "
                "COUNT(*) AS total_transactions "
                "FROM analytics.fct_transactions LIMIT 1000;"
            )

        if "volume" in user_q:
            return (
                "SELECT "
                "SUM(transaction_amount_eur) AS gross_transaction_volume_eur, "
                "COUNT(*) AS total_transaction_count "
                "FROM analytics.fct_transactions LIMIT 1000;"
            )

        if "take rate" in user_q:
            return (
                "SELECT "
                "ROUND((SUM(net_recognized_revenue_eur) / NULLIF(SUM(gross_assessed_fee_amount_eur), 0) * 100)::numeric, 2) AS effective_take_rate_pct, "
                "SUM(net_recognized_revenue_eur) AS net_revenue_eur, "
                "SUM(gross_assessed_fee_amount_eur) AS gross_fees_eur "
                "FROM analytics.fct_customer_revenue LIMIT 1000;"
            )

        # Default: Net Recognized Revenue Total with complete reconciliation bridge
        return (
            "SELECT "
            "SUM(gross_assessed_fee_amount_eur) AS gross_assessed_fee_amount_eur, "
            "SUM(waived_fee_amount_eur) AS waived_fee_amount_eur, "
            "SUM(net_collectible_fee_amount_eur) AS net_collectible_fee_amount_eur, "
            "SUM(collected_fee_amount_eur) AS collected_fee_amount_eur, "
            "SUM(outstanding_fee_amount_eur) AS outstanding_fee_amount_eur, "
            "SUM(reversed_revenue_amount_eur) AS reversed_revenue_amount_eur, "
            "SUM(pass_through_cost_amount_eur) AS pass_through_cost_amount_eur, "
            "SUM(net_recognized_revenue_eur) AS net_recognized_revenue_eur "
            "FROM analytics.fct_customer_revenue LIMIT 1000;"
        )

    def _generate_mock_answer(self, prompt: str, user_q: str) -> str:
        """Produce accurate financial answer dynamically derived from query result rows."""
        rows = self._extract_query_rows(prompt)

        # 0. Entity counts (descriptive row counts)
        count_target = self._count_target(user_q)
        if count_target:
            model, alias = count_target
            entity = alias.replace("total_", "")
            if rows and alias in rows[0]:
                total = int(rows[0][alias])
                return (
                    f"There are **{total:,} {entity}** in the certified `analytics.{model}` mart. "
                    "This is a descriptive row count of the warehouse entity, not a financial metric."
                )
            return f"No {entity} records were returned."

        # 1. Fee Collection Rate
        if "collection rate" in user_q or "collected fees" in user_q or "realiz" in user_q:
            if rows:
                r0 = rows[0]
                rate = float(r0.get("fee_collection_rate_pct", 0.0))
                coll = float(r0.get("total_collected_eur", 0.0))
                tot = float(r0.get("total_collectible_eur", 0.0))
                return (
                    f"Our overall fee collection realization rate is **{rate:.2f}%**. "
                    f"Out of €{tot:,.2f} in net collectible fees, €{coll:,.2f} was successfully collected and settled "
                    "from customer accounts into bank cash accounts."
                )
            return "Our fee collection realization rate query returned no records."

        # 2. Top Customers by Revenue
        if "top customer" in user_q or "most revenue" in user_q or "which customer" in user_q:
            if rows:
                top = rows[0]
                name = top.get("customer_name", "Top Client")
                seg = top.get("customer_segment", "Commercial")
                rev = float(top.get("recognized_revenue_eur", 0.0))
                count = len(rows)
                return (
                    f"The top revenue-generating customer is **{name}** ({seg}), "
                    f"contributing **€{rev:,.2f}** in net recognized revenue. "
                    f"A total of {count} client relationships were ranked in this analysis."
                )
            return "No customer revenue records matched the query criteria."

        # 3. Transaction Reversal Rate
        if "revers" in user_q or "chargeback" in user_q or "cancell" in user_q:
            if rows:
                r0 = rows[0]
                rate = float(r0.get("reversal_rate_pct", 0.0))
                rev_cnt = int(r0.get("reversed_count", 0))
                tot_cnt = int(r0.get("total_transactions", 0))
                return (
                    f"The commercial transaction reversal rate is **{rate:.2f}%** "
                    f"({rev_cnt} reversed movements out of {tot_cnt:,} total transactions)."
                )
            return "No transaction reversal records were identified."

        # 4. Billing Exceptions & Outstanding Arrears
        if (
            "outstanding" in user_q
            or "exception" in user_q
            or "arrears" in user_q
            or "past due" in user_q
        ):
            if rows:
                r0 = rows[0]
                # Check if this is the portfolio-level summary query
                if "total_exception_count" in r0:
                    ex_count = int(r0.get("total_exception_count", 0))
                    cust_count = int(r0.get("impacted_customers_count", 0))
                    tot_arrears = float(r0.get("total_arrears_eur", 0.0))
                    tot_assessments = int(r0.get("total_assessment_count", 0))
                    rate = float(r0.get("billing_exception_rate_pct", 0.0))
                    return (
                        f"There are **{ex_count} billing exception assessments** currently outstanding across "
                        f"**{cust_count} commercial clients**, with uncollected fee arrears totaling **€{tot_arrears:,.2f}**. "
                        f"This represents a **{rate:.2f}%** billing exception rate across the "
                        f"**{tot_assessments:,} total fee assessments** in the portfolio. "
                        "All figures are unified in EUR reporting currency using synthetic daily mid-market FX rates."
                    )

                # Otherwise, this is the grouped customer exposure breakdown query
                top = rows[0]
                top_name = top.get("customer_name", "Top Client")
                top_seg = top.get("customer_segment", "Commercial")
                top_fee = top.get("fee_type", "FEE")
                top_eur = float(top.get("outstanding_amount_eur", 0.0))
                top_assess = int(top.get("assessment_count", 1))

                tot_arrears_sample = sum(float(r.get("outstanding_amount_eur", 0.0)) for r in rows)
                tot_assessments_sample = sum(int(r.get("assessment_count", 1)) for r in rows)
                segment_count = len(rows)

                return (
                    f"Uncollected fee arrears are led by **{top_name}** ({top_seg}) with **€{top_eur:,.2f}** "
                    f"in EUR-converted arrears across **{top_assess} fee assessments** for {top_fee}. "
                    f"Across the **{segment_count} grouped client/product exposure segments** in this view, "
                    f"arrears total **€{tot_arrears_sample:,.2f}** across **{tot_assessments_sample} individual fee assessments**."
                )
            return "There are currently no outstanding billing exceptions or fee arrears."

        # 5. Customer Segments
        if "segment" in user_q or "profitab" in user_q:
            if rows:
                top = rows[0]
                seg = top.get("customer_segment", "Commercial")
                rev = float(top.get("recognized_revenue_eur", 0.0))
                return (
                    f"Revenue by customer segment shows **{seg}** delivering the largest share of net recognized revenue "
                    f"at **€{rev:,.2f}**."
                )
            return "No segment revenue records were found."

        # 6. Gross Assessed Fees
        if "assess" in user_q:
            if rows:
                tot_assessed = sum(float(r.get("total_assessed_amount", 0.0)) for r in rows)
                return f"Total gross assessed fees across currencies reached **€{tot_assessed:,.2f}** prior to fee waivers."
            return "No fee assessment records were returned."

        # 7. Waived Fees
        if "waiv" in user_q:
            if rows:
                tot_waived = sum(float(r.get("total_waived_eur", 0.0)) for r in rows)
                return f"Contractual and relationship fee waivers totaled **€{tot_waived:,.2f}** across commercial accounts."
            return "No waived fee records were returned."

        # 8. Transaction Volume
        if "volume" in user_q:
            if rows:
                r0 = rows[0]
                vol = float(r0.get("gross_transaction_volume_eur", 0.0))
                cnt = int(r0.get("total_transaction_count", 0))
                return f"Gross transaction volume processed reached **€{vol:,.2f}** across {cnt:,} transactions."
            return "No transaction volume records were returned."

        # 9. Effective Take Rate
        if "take rate" in user_q:
            if rows:
                r0 = rows[0]
                rate = float(r0.get("effective_take_rate_pct", 0.0))
                net = float(r0.get("net_revenue_eur", 0.0))
                gross = float(r0.get("gross_fees_eur", 0.0))
                return (
                    f"The effective fee realization take rate is **{rate:.2f}%** "
                    f"(€{net:,.2f} in net recognized revenue on €{gross:,.2f} gross assessed fee potential)."
                )
            return "No fee realization records were returned."

        # 10. Net Recognized Revenue (Default) with complete accounting reconciliation
        if rows:
            r0 = rows[0]
            net_rev = float(r0.get("net_recognized_revenue_eur", 0.0))
            gross = float(r0.get("gross_assessed_fee_amount_eur", 0.0))
            waived = float(r0.get("waived_fee_amount_eur", 0.0))
            net_collectible = float(r0.get("net_collectible_fee_amount_eur", gross - waived))
            collected = float(r0.get("collected_fee_amount_eur", 0.0))
            arrears = float(r0.get("outstanding_fee_amount_eur", net_collectible - collected))
            reversals = float(r0.get("reversed_revenue_amount_eur", 0.0))
            pass_through = float(
                r0.get("pass_through_cost_amount_eur", collected - reversals - net_rev)
            )
            reconciled_diff = net_collectible - net_rev

            return (
                f"Total net recognized commercial revenue is **€{net_rev:,.2f}**. "
                f"This reflects the reconciled accounting formula: gross contractual assessed fees of **€{gross:,.2f}** "
                f"less fee waivers of **€{waived:,.2f}** yields net collectible fees of **€{net_collectible:,.2f}**; "
                f"deducting uncollected arrears of **€{arrears:,.2f}** yields collected fee revenue of **€{collected:,.2f}**; "
                f"and deducting fee reversals of **€{reversals:,.2f}** and pass-through clearing/network costs of **€{pass_through:,.2f}** "
                f"fully reconciles the **€{reconciled_diff:,.2f}** difference to net recognized revenue."
            )

        return "Query executed successfully against the analytics warehouse, but 0 records were returned."
