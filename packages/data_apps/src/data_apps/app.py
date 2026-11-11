"""Executive Financial Analytics Dashboard & AI Copilot for Commercial Banking.

Provides dynamic financial KPI monitoring, revenue trends, customer rankings,
billing arrears reconciliation, and natural-language financial analytics
backed by governed PostgreSQL analytical marts.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

# Ensure monorepo package source roots are in sys.path for standalone Streamlit Cloud execution
_REPO_ROOT = Path(__file__).resolve().parents[4]
for _pkg in ["shared", "data_platform", "ai_services", "data_apps"]:
    _pkg_src = _REPO_ROOT / "packages" / _pkg / "src"
    if _pkg_src.exists() and str(_pkg_src) not in sys.path:
        sys.path.insert(0, str(_pkg_src))

# Standalone cloud deployment: Streamlit Community Cloud has no local PostgreSQL. When no external
# database host is configured and nothing is listening on the local Postgres port, use the
# embedded DuckDB marts. A reachable local PostgreSQL (development) is left untouched.
if "DATABASE_BACKEND" not in os.environ and os.environ.get("POSTGRES_HOST") in (
    None,
    "",
    "localhost",
    "127.0.0.1",
):
    import socket

    try:
        with socket.create_connection(
            ("127.0.0.1", int(os.environ.get("POSTGRES_PORT", "5432"))), timeout=0.15
        ):
            pass
    except OSError:
        os.environ["DATABASE_BACKEND"] = "duckdb"

# Streamlit keeps imported modules (and lru_cache state) alive across redeploys/reruns.
# Reset cached settings so the backend selected above is always honoured.
from shared.config import get_settings as _get_settings_for_reset  # noqa: E402

_get_settings_for_reset.cache_clear()

import httpx
import pandas as pd
import streamlit as st
from ai_services.api.analytics_service import AnalyticsDataService
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.schemas import (
    AnalyticsQueryResponse,
    BillingArrearsResponse,
    CustomerRankingsResponse,
    FinancialOverviewResponse,
    HealthResponse,
    RevenueTrendsResponse,
)
from data_platform.metadata.service import MetadataService
from shared.config import get_settings

logger = logging.getLogger(__name__)

# Configure Streamlit Page
st.set_page_config(
    page_title="Commercial Banking AI Analytics Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


def display_dataframe(data: Any, **kwargs: Any) -> Any:
    """Display dataframe adapting seamlessly to Streamlit width conventions."""
    try:
        return st.dataframe(data, width="stretch", **kwargs)
    except TypeError:
        return st.dataframe(data, use_container_width=True, **kwargs)


@st.cache_resource
def get_graph():
    """Build and cache the compiled LangGraph workflow."""
    return build_financial_analytics_graph()


def get_backend_client() -> tuple[str | None, dict[str, str]]:
    """Return backend base URL and auth headers if REST API integration is active."""
    cfg = get_settings()
    if cfg.api_base_url:
        headers: dict[str, str] = {}
        if cfg.api_key:
            headers["X-API-Key"] = cfg.api_key
        return cfg.api_base_url.rstrip("/"), headers
    return None, {}


def load_health_probe(use_test_db: bool) -> HealthResponse:
    """Check system and warehouse health via REST API or direct service."""
    base_url, headers = get_backend_client()
    target_env = "test" if use_test_db else "dev"
    if base_url:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{base_url}/api/v1/analytics/health?environment={target_env}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return HealthResponse.model_validate(resp.json())
        except Exception as exc:
            logger.warning("API health probe failed, using direct DB check: %s", exc)

    return AnalyticsDataService.get_health_probe(use_test_db=use_test_db)


@st.cache_data(ttl=30)
def load_catalog_data():
    """Fetch governed metrics and queryable models from the metadata catalog."""
    meta = MetadataService()
    try:
        metrics = meta.list_metrics()
        models = meta.list_queryable_models()
        return metrics, models
    except Exception as exc:
        logger.warning("Could not load catalog data: %s", exc)
        return [], []


@st.cache_data(ttl=30)
def load_overview_data(use_test_db: bool) -> tuple[FinancialOverviewResponse | None, str | None]:
    """Load executive financial overview metrics dynamically from REST API or warehouse."""
    base_url, headers = get_backend_client()
    target_env = "test" if use_test_db else "dev"
    if base_url:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{base_url}/api/v1/analytics/overview?environment={target_env}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return FinancialOverviewResponse.model_validate(resp.json()), None
        except Exception as exc:
            logger.warning("API call failed for overview, falling back: %s", exc)

    try:
        return AnalyticsDataService.get_financial_overview(use_test_db=use_test_db), None
    except Exception as exc:
        backend = get_settings().database_backend
        logger.exception("Failed loading overview metrics (backend=%s): %s", backend, exc)
        return None, f"[backend={backend}] {exc}"


@st.cache_data(ttl=30)
def load_trends_data(use_test_db: bool):
    """Load monthly revenue and fee collection trends."""
    base_url, headers = get_backend_client()
    target_env = "test" if use_test_db else "dev"
    if base_url:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{base_url}/api/v1/analytics/trends?environment={target_env}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return RevenueTrendsResponse.model_validate(resp.json()).trends
        except Exception as exc:
            logger.warning("API call failed for trends, falling back: %s", exc)

    try:
        res = AnalyticsDataService.get_monthly_trends(use_test_db=use_test_db)
        return res.trends
    except Exception as exc:
        logger.error("Failed loading trends: %s", exc)
        return []


@st.cache_data(ttl=30)
def load_customer_rankings(use_test_db: bool, limit: int = 50, segment: str | None = None):
    """Load customer revenue rankings."""
    base_url, headers = get_backend_client()
    target_env = "test" if use_test_db else "dev"
    if base_url:
        try:
            params = f"environment={target_env}&limit={limit}"
            if segment:
                params += f"&segment={segment}"
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{base_url}/api/v1/analytics/customers?{params}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return CustomerRankingsResponse.model_validate(resp.json()).customers
        except Exception as exc:
            logger.warning("API call failed for customer rankings, falling back: %s", exc)

    try:
        res = AnalyticsDataService.get_customer_rankings(
            use_test_db=use_test_db, limit=limit, segment=segment
        )
        return res.customers
    except Exception as exc:
        logger.error("Failed loading customer rankings: %s", exc)
        return []


@st.cache_data(ttl=30)
def load_arrears_data(use_test_db: bool, limit: int = 100) -> BillingArrearsResponse | None:
    """Load billing arrears breakdown."""
    base_url, headers = get_backend_client()
    target_env = "test" if use_test_db else "dev"
    if base_url:
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(
                    f"{base_url}/api/v1/analytics/arrears?environment={target_env}&limit={limit}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    return BillingArrearsResponse.model_validate(resp.json())
        except Exception as exc:
            logger.warning("API call failed for arrears, falling back: %s", exc)

    try:
        return AnalyticsDataService.get_billing_arrears(use_test_db=use_test_db, limit=limit)
    except Exception as exc:
        logger.error("Failed loading arrears data: %s", exc)
        return None


def format_eur(val: float | None) -> str:
    """Format numeric values as European currency standard."""
    if val is None:
        return "€0.00"
    return f"€{val:,.2f}"


def main():
    # Sidebar: Runtime & Governance Controls
    st.sidebar.title("🏦 Banking Platform")
    st.sidebar.caption("Executive Analytics & AI Copilot")

    env_option = st.sidebar.selectbox(
        "Warehouse Environment",
        options=["DEV (Showcase: 50 Clients, 5k Txns)", "TEST (Isolation: 10 Clients, 200 Txns)"],
        index=0,
    )
    target_env = "dev" if "DEV" in env_option else "test"
    use_test_db = target_env == "test"

    cfg = get_settings()
    backend_label = "DuckDB (Packaged Marts)" if cfg.is_duckdb else "PostgreSQL 16"

    # Live Health Probe
    health = load_health_probe(use_test_db=use_test_db)
    if health.status == "UP":
        latency_text = (
            f" ({health.database_latency_ms:.1f}ms)" if health.database_latency_ms else ""
        )
        st.sidebar.success(f"Warehouse: {backend_label}{latency_text}")
    else:
        st.sidebar.error(f"Warehouse: {health.database}")

    base_url, _ = get_backend_client()
    connection_mode = (
        f"🌐 REST API (`{base_url}`)" if base_url else "⚡ Direct Python Service (In-Process)"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🤖 AI Inference Engine")
    is_live = cfg.llm_provider != "mock" and bool(cfg.llm_api_key)
    if is_live:
        st.sidebar.success(f"🟢 **Live LLM**: `{cfg.llm_model}`")
    else:
        st.sidebar.info("🧪 **Demo Mode**: Deterministic Mock Provider")
    st.sidebar.caption(
        f"• **Architecture**: LangGraph State Machine\n"
        f"• **Service Tier**: {connection_mode}\n"
        f"• **Safety**: SQLGlot AST Validation"
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🔒 Governance & Security")
    role_desc = (
        "In-Memory Read-Only Views" if cfg.is_duckdb else "`analytics_reader` (Least Privilege)"
    )
    st.sidebar.caption(
        f"• **Role**: {role_desc}\n"
        "• **AST Validation**: SQLGlot SELECT-only\n"
        "• **Timeout**: 5000ms Statement Limit\n"
        "• **Data Source**: Governed Showcase Marts"
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # Main Header
    st.title("Enterprise AI Analytics Platform — Financial Services")
    st.caption(
        f"Active Warehouse Target: **{target_env.upper()}** (`{'analytics_platform_test' if use_test_db else 'analytics_platform'}`) | "
        "Dimensional Marts: `analytics.fct_customer_revenue`, `analytics.fct_fee_assessments`, `analytics.fct_transactions`"
    )

    # 5 Tab Executive Layout
    tab_overview, tab_customers, tab_arrears, tab_copilot, tab_catalog = st.tabs(
        [
            "📊 Executive Overview",
            "👥 Customer Rankings",
            "⚠️ Billing Arrears",
            "🤖 AI Financial Copilot",
            "📚 Governed Catalog",
        ]
    )

    overview_data, overview_err = load_overview_data(use_test_db)

    # -------------------------------------------------------------
    # TAB 1: Executive Overview & Financial KPIs
    # -------------------------------------------------------------
    with tab_overview:
        st.subheader("Executive Financial Performance")
        if overview_data:
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric(
                    label="Net Recognized Revenue",
                    value=format_eur(overview_data.net_recognized_revenue_eur),
                    delta="Accrued Accounting Revenue",
                    help="Net recognized banking fee revenue under accrual accounting: Collected Fees - Reversals - Pass-Through Costs.",
                )
            with col2:
                st.metric(
                    label="Effective Take Rate",
                    value=f"{overview_data.effective_take_rate_pct:.2f}%",
                    delta=f"{overview_data.volume_take_rate_bps:.2f} bps Volume Yield",
                    help="Effective Fee Realization Rate: (Net Recognized Revenue / Gross Assessed Fees) * 100. Secondary: Commercial Volume Take Rate in bps.",
                )
            with col3:
                st.metric(
                    label="Cash Collection Realization",
                    value=f"{overview_data.fee_collection_rate_pct:.2f}%",
                    delta="Cash Swept / Collectible",
                    help="Fee Collection Realization Rate: (Cash Collected Fees / Net Collectible Fees) * 100.",
                )
            with col4:
                st.metric(
                    label="Billing Exception Rate",
                    value=f"{overview_data.billing_exception_rate_pct:.2f}%",
                    delta=f"{overview_data.total_exception_count} / {overview_data.total_assessments_count} fees",
                    delta_color="inverse",
                    help="Proportion of fee assessments in arrears: (Outstanding Assessments / Total Assessments) * 100.",
                )
            with col5:
                st.metric(
                    label="Outstanding Arrears",
                    value=format_eur(overview_data.uncollected_arrears_eur),
                    delta=f"{overview_data.impacted_customers_count} clients in arrears",
                    delta_color="inverse",
                    help="Total uncollected fee balances currently in arrears across client accounts.",
                )

            st.caption(
                f"💳 **Commercial Payment Volume**: {format_eur(overview_data.gross_transaction_volume_eur)} processed across "
                f"**{overview_data.total_transactions_count:,}** transactions | Volume Take Rate: **{overview_data.volume_take_rate_bps:.2f} bps**"
            )

            st.markdown("---")

            # Revenue Accounting Reconciliation Bridge
            st.markdown("#### Governed Revenue Accounting Bridge")
            bridge_cols = st.columns(7)
            bridge_cols[0].metric(
                "Gross Assessed",
                format_eur(overview_data.gross_assessed_fees_eur),
                help="Contractual fee potential assessed on commercial movements.",
            )
            bridge_cols[1].metric(
                "Less Waivers",
                f"-{format_eur(overview_data.fee_waivers_eur)}",
                help="Fee concessions and commercial discounts granted.",
            )
            bridge_cols[2].metric(
                "Net Collectible",
                format_eur(overview_data.net_collectible_fees_eur),
                help="Collectible fee pool (Gross Assessed - Waivers).",
            )
            bridge_cols[3].metric(
                "Cash Collected",
                format_eur(overview_data.collected_fees_eur),
                help=f"Actual cash swept to bank accounts (Uncollected arrears: -{format_eur(overview_data.uncollected_arrears_eur)}).",
            )
            bridge_cols[4].metric(
                "Less Reversals",
                f"-{format_eur(overview_data.reversed_revenue_eur)}",
                help="Fee settlements reversed due to dispute, cancellation, or correction.",
            )
            bridge_cols[5].metric(
                "Less Pass-Through",
                f"-{format_eur(overview_data.pass_through_costs_eur)}",
                help="Direct network clearing, card scheme, and interchange pass-through costs.",
            )
            bridge_cols[6].metric(
                "Net Recognized",
                format_eur(overview_data.net_recognized_revenue_eur),
                help="Final net revenue recognized on General Ledger: Cash Collected - Reversals - Pass-Through Costs.",
            )

            st.info(
                f"**Reconciliation Equation**: Cash Collected ({format_eur(overview_data.collected_fees_eur)}) "
                f"− Reversals ({format_eur(overview_data.reversed_revenue_eur)}) "
                f"− Pass-Through Costs ({format_eur(overview_data.pass_through_costs_eur)}) "
                f"= **Net Recognized Revenue ({format_eur(overview_data.net_recognized_revenue_eur)})**"
            )

            # Monthly Trends Chart
            st.markdown("#### Monthly Revenue & Fee Collection Trends")
            trends = load_trends_data(use_test_db)
            if trends:
                trends_df = pd.DataFrame([t.model_dump() for t in trends])
                trends_df = trends_df.rename(
                    columns={
                        "month": "Month",
                        "net_revenue_eur": "Net Revenue (EUR)",
                        "gross_fees_eur": "Gross Fees (EUR)",
                        "collected_fees_eur": "Collected Cash (EUR)",
                    }
                )
                chart_data = trends_df.set_index("Month")[
                    ["Net Revenue (EUR)", "Gross Fees (EUR)", "Collected Cash (EUR)"]
                ]
                st.line_chart(chart_data)

                with st.expander("View Monthly Performance Breakdown Data"):
                    display_dataframe(trends_df)
                    csv_trends = trends_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label="📥 Download Monthly Trends CSV",
                        data=csv_trends,
                        file_name=f"monthly_revenue_trends_{target_env}.csv",
                        mime="text/csv",
                    )
        else:
            st.error("Could not retrieve executive overview metrics from analytical warehouse.")
            if overview_err:
                st.warning(f"Diagnostic error details: `{overview_err}`")
            if st.button("🔄 Reload Data / Reset Cache", key="reload_overview_btn"):
                st.cache_data.clear()
                st.rerun()

    # -------------------------------------------------------------
    # TAB 2: Customer Revenue & Rankings
    # -------------------------------------------------------------
    with tab_customers:
        st.subheader("Customer Revenue Leaderboard")

        filter_col1, filter_col2 = st.columns([1, 3])
        with filter_col1:
            segment_choice = st.selectbox(
                "Filter Segment",
                options=["ALL", "INSTITUTIONAL", "COMMERCIAL_SME", "CORPORATE"],
                index=0,
            )
            selected_segment = None if segment_choice == "ALL" else segment_choice

        customers = load_customer_rankings(use_test_db, limit=50, segment=selected_segment)
        if customers:
            cust_df = pd.DataFrame([c.model_dump() for c in customers])
            cust_df = cust_df.rename(
                columns={
                    "customer_id": "Client ID",
                    "customer_name": "Client Name",
                    "customer_segment": "Segment",
                    "net_revenue_eur": "Net Revenue (EUR)",
                    "gross_fees_eur": "Gross Assessed (EUR)",
                    "collected_fees_eur": "Collected (EUR)",
                    "outstanding_arrears_eur": "Arrears (EUR)",
                }
            )

            with filter_col2:
                st.caption(f"Displaying top **{len(cust_df)}** commercial clients by net revenue.")

            display_dataframe(
                cust_df.style.format(
                    {
                        "Net Revenue (EUR)": "€{:,.2f}",
                        "Gross Assessed (EUR)": "€{:,.2f}",
                        "Collected (EUR)": "€{:,.2f}",
                        "Arrears (EUR)": "€{:,.2f}",
                    }
                ),
            )

            csv_cust = cust_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Customer Leaderboard CSV",
                data=csv_cust,
                file_name=f"customer_rankings_{target_env}.csv",
                mime="text/csv",
            )
        else:
            st.info("No customer revenue records found matching filter.")

    # -------------------------------------------------------------
    # TAB 3: Billing Arrears & Exceptions
    # -------------------------------------------------------------
    with tab_arrears:
        st.subheader("Billing Arrears & Exception Registry")
        arrears_resp = load_arrears_data(use_test_db)
        if arrears_resp:
            a_col1, a_col2, a_col3 = st.columns(3)
            a_col1.metric("Total Outstanding Arrears", format_eur(arrears_resp.total_arrears_eur))
            a_col2.metric(
                "Exception Fee Assessments", f"{arrears_resp.total_exception_count} items"
            )
            a_col3.metric(
                "Impacted Commercial Clients", f"{arrears_resp.impacted_customers_count} clients"
            )

            st.markdown("---")
            if arrears_resp.exceptions:
                arr_df = pd.DataFrame([e.model_dump() for e in arrears_resp.exceptions])
                arr_df = arr_df.rename(
                    columns={
                        "customer_id": "Client ID",
                        "customer_name": "Client Name",
                        "customer_segment": "Segment",
                        "fee_type": "Fee Category",
                        "currency": "Ccy",
                        "exception_count": "Exceptions",
                        "outstanding_native": "Native Arrears",
                        "outstanding_eur": "EUR Arrears",
                    }
                )

                display_dataframe(
                    arr_df.style.format(
                        {
                            "Native Arrears": "{:,.2f}",
                            "EUR Arrears": "€{:,.2f}",
                        }
                    ),
                )

                csv_arr = arr_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Arrears Registry CSV",
                    data=csv_arr,
                    file_name=f"billing_arrears_{target_env}.csv",
                    mime="text/csv",
                )
            else:
                st.success("Zero billing exceptions detected in target warehouse.")
        else:
            st.error("Failed to load billing arrears records.")

    # -------------------------------------------------------------
    # TAB 4: AI Financial Copilot (Natural Language Analytics)
    # -------------------------------------------------------------
    with tab_copilot:
        st.subheader("Governed AI Financial Inquiry")
        st.caption(
            "Natural-language question answering grounded in certified dbt analytical models with SQLGlot validation."
        )

        cfg = get_settings()
        is_live_llm = cfg.llm_provider != "mock" and bool(cfg.llm_api_key)
        engine_label = (
            f"🟢 Live Model (`{cfg.llm_model}`)"
            if is_live_llm
            else "🧪 Safe Demo Mode (Deterministic Mock LLM)"
        )
        st.info(
            f"**Active Inference Engine**: {engine_label} — Queries execute read-only against the `{target_env.upper()}` marts ({'embedded DuckDB' if cfg.is_duckdb else 'PostgreSQL analytics_reader'})."
        )

        # Suggested Prompt Buttons (First-time visitors)
        st.markdown("**💡 Common Business Inquiries (Click to Ask):**")
        p_row1_col1, p_row1_col2, p_row1_col3 = st.columns(3)
        p_row2_col1, p_row2_col2, p_row2_col3 = st.columns(3)
        sample_prompt = None

        if p_row1_col1.button("💰 Net Recognized Revenue", use_container_width=True):
            sample_prompt = "What was our total net recognized revenue?"
        if p_row1_col2.button("🏆 Top Revenue Customers", use_container_width=True):
            sample_prompt = "Which customers generated the most revenue?"
        if p_row1_col3.button("📈 Effective Take Rate", use_container_width=True):
            sample_prompt = "What was our effective fee realization take rate?"
        if p_row2_col1.button("💳 Fee Collection Realization", use_container_width=True):
            sample_prompt = "What is our overall fee collection rate?"
        if p_row2_col2.button("⚠️ Billing Arrears & Exceptions", use_container_width=True):
            sample_prompt = "Are there outstanding fees that need attention?"
        if p_row2_col3.button("🔄 Transaction Reversals", use_container_width=True):
            sample_prompt = "How much commercial fee revenue was reversed?"

        st.markdown("---")

        # Session Conversation History
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # History Header with Clear Control
        hist_col1, hist_col2 = st.columns([5, 1])
        hist_col1.markdown(f"#### Conversation History ({len(st.session_state.messages)} messages)")
        if hist_col2.button("🗑️ Clear History", use_container_width=True, key="clear_chat_tab_btn"):
            st.session_state.messages = []
            st.rerun()

        # Conversation area: filled after input handling so each answer renders exactly once.
        history_box = st.container()

        # Single question box (suggested-prompt buttons above feed the same pipeline)
        st.markdown("#### Ask a Question")
        with st.form("copilot_query_form", clear_on_submit=True):
            form_col_input, form_col_btn = st.columns([5, 1])
            with form_col_input:
                user_typed = st.text_input(
                    "Enter a financial inquiry:",
                    placeholder="e.g. 'What was our net revenue?', 'How many customers do we have?', 'Which customers generated the most revenue?'",
                    key="copilot_form_text",
                    label_visibility="collapsed",
                )
            with form_col_btn:
                form_submitted = st.form_submit_button(
                    "Ask Copilot 🚀", type="primary", use_container_width=True
                )

        query_to_run = sample_prompt or (user_typed.strip() if form_submitted else "") or None

        with history_box:
            for idx, msg in enumerate(st.session_state.messages):
                with st.chat_message(msg["role"]):
                    if msg["role"] == "user":
                        st.markdown(msg["content"])
                    else:
                        _render_assistant_response(msg["response"], key_prefix=f"hist_{idx}")

            if query_to_run:
                st.session_state.messages.append({"role": "user", "content": query_to_run})
                with st.chat_message("user"):
                    st.markdown(query_to_run)

                with (
                    st.chat_message("assistant"),
                    st.spinner("Analyzing question, validating SQL, and querying the warehouse..."),
                ):
                    base_url, headers = get_backend_client()
                    resp = None
                    if base_url:
                        try:
                            with httpx.Client(timeout=30.0) as client:
                                api_resp = client.post(
                                    f"{base_url}/api/v1/analytics/ask",
                                    json={"question": query_to_run, "environment": target_env},
                                    headers=headers,
                                )
                                if api_resp.status_code == 200:
                                    resp = AnalyticsQueryResponse.model_validate(api_resp.json())
                        except Exception as exc:
                            logger.warning(
                                "AI query to API backend failed, falling back to local graph: %s",
                                exc,
                            )

                    if resp is None:
                        graph = get_graph()
                        result = graph.invoke({"question": query_to_run, "environment": target_env})
                        resp = result.get("final_response")

                    if resp:
                        st.session_state.messages.append({"role": "assistant", "response": resp})
                        _render_assistant_response(
                            resp, key_prefix=f"hist_{len(st.session_state.messages) - 1}"
                        )

    # -------------------------------------------------------------
    # TAB 5: Governed Metric Catalog & Data Dictionary
    # -------------------------------------------------------------
    with tab_catalog:
        st.subheader("Certified Governance Catalog")
        metrics, models = load_catalog_data()

        st.markdown("#### 12 Governed Financial Metrics")
        if metrics:
            metrics_table = [
                {
                    "Metric ID": m.metric_id,
                    "Name": m.metric_name,
                    "Source Model": f"analytics.{m.source_model}",
                    "Formula": m.formula,
                    "Grain": m.grain,
                    "Business Definition": m.business_definition,
                    "Currency Treatment": m.native_currency_treatment,
                }
                for m in metrics
            ]
            display_dataframe(pd.DataFrame(metrics_table))

        st.markdown("#### Queryable Dimensional Marts (`analytics` schema)")
        if models:
            for model in models:
                m_name = getattr(model, "name", getattr(model, "model_name", "unknown"))
                with st.expander(f"📦 analytics.{m_name}"):
                    st.markdown(f"**Grain**: `{model.grain or 'N/A'}`")
                    st.markdown(f"**Description**: {model.description}")
                    if hasattr(model, "columns") and model.columns:
                        cols_list = (
                            model.columns.values()
                            if isinstance(model.columns, dict)
                            else model.columns
                        )
                        cols_df = pd.DataFrame(
                            [
                                {
                                    "Column": getattr(c, "name", str(c)),
                                    "Type": getattr(c, "data_type", "TEXT"),
                                    "Description": getattr(
                                        c, "description", "Undocumented column."
                                    ),
                                }
                                for c in cols_list
                            ]
                        )
                        display_dataframe(cols_df)


def _render_assistant_response(resp: AnalyticsQueryResponse, key_prefix: str = "resp"):
    """Render executive financial narrative, evidence data table, and SQL audit drawer."""
    if resp.status == "OUT_OF_SCOPE":
        st.warning(f"**Inquiry Out of Scope**: {resp.answer}")
        return

    if resp.status == "REJECTED":
        st.error(resp.answer)
        if resp.sql_query:
            with st.expander("Inspected SQL Expression", expanded=False):
                st.code(resp.sql_query, language="sql")
        return

    if resp.status == "ERROR":
        st.error(f"**Database Error**: {resp.answer}")
        return

    # Success Narrative
    st.markdown(resp.answer)

    cfg = get_settings()
    is_live = cfg.llm_provider != "mock" and bool(cfg.llm_api_key)
    demo_tag = f"`{cfg.llm_model}`" if is_live else "`Mock (Demo)`"

    # Metadata & Performance Badge
    badge_cols = st.columns(5)
    if resp.metric_used:
        badge_cols[0].caption(f"**Metric**: `{resp.metric_used}`")
    if resp.model_used:
        badge_cols[1].caption(f"**Model**: `analytics.{resp.model_used}`")
    if resp.execution_time_ms is not None:
        badge_cols[2].caption(f"**Latency**: `{resp.execution_time_ms:.1f}ms`")
    if resp.row_count is not None:
        badge_cols[3].caption(f"**Rows**: `{resp.row_count}`")
    badge_cols[4].caption(f"**Engine**: {demo_tag}")

    # Result Evidence Data Table
    if resp.data and len(resp.data) > 0:
        with st.expander("📊 View Result Records", expanded=True):
            df = pd.DataFrame(resp.data)
            display_dataframe(df)
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Result Data CSV",
                data=csv_data,
                file_name="query_results.csv",
                mime="text/csv",
                key=f"download_{key_prefix}",
            )

    # Governed SQL & Security Audit Drawer
    with st.expander("🔍 Governed SQL & Security Verification", expanded=False):
        st.markdown(
            "**Executed SQL (read-only, "
            + ("embedded DuckDB marts" if cfg.is_duckdb else "PostgreSQL `analytics_reader`")
            + "):**"
        )
        if resp.sql_query:
            st.code(resp.sql_query, language="sql")
        st.caption(
            "🔒 **Boundary Controls**: Single SELECT statement | AST validated via SQLGlot | "
            "Restricted to `analytics` schema allowlist | 5000ms statement timeout | Clamped to 1000 rows."
        )
        if resp.limitations:
            st.info(f"**Reporting Limitations**: {resp.limitations}")


if __name__ == "__main__":
    main()
