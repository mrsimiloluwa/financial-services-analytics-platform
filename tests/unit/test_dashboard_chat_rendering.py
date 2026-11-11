"""Regression tests for the Copilot chat tab and entity-count questions (DuckDB mode)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ai_services.graph.workflow import build_financial_analytics_graph
from ai_services.providers.mock import DeterministicMockLLMProvider
from shared.config import get_settings
from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[2] / "packages/data_apps/src/data_apps/app.py"


@pytest.fixture(autouse=True)
def duckdb_backend(monkeypatch):
    monkeypatch.setenv("DATABASE_BACKEND", "duckdb")
    monkeypatch.setenv("POSTGRES_HOST", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _ask(at: AppTest, question: str) -> None:
    at.text_input(key="copilot_form_text").set_value(question)
    next(b for b in at.button if "Ask Copilot" in b.label).click()
    at.run()


def test_single_question_input_and_no_duplicate_element_ids():
    """Asking several questions re-renders earlier answers from history without ID clashes."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()
    assert not at.exception
    assert len(at.chat_input) == 0, "Copilot must expose exactly one question box"
    assert len(at.text_input) == 1

    for question in (
        "How many customers do we have?",
        "What was our total net recognized revenue?",
        "Which customers generated the most revenue?",
    ):
        _ask(at, question)
        assert not at.exception, f"Crash after asking: {question}"

    assert len(at.session_state.messages) == 6


@pytest.mark.parametrize(
    ("question", "model", "expected_count"),
    [
        ("How many customers do we have?", "dim_customers", 50),
        ("how many clients are there", "dim_customers", 50),
        ("How many accounts?", "dim_accounts", 111),
        ("How many transactions were processed?", "fct_transactions", 5000),
    ],
)
def test_entity_count_questions_answer_the_question_asked(question, model, expected_count):
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    resp = graph.invoke({"question": question, "environment": "dev"})["final_response"]
    assert resp.status == "SUCCESS"
    assert resp.model_used == model
    assert f"{expected_count:,}" in resp.answer
    assert "€" not in resp.answer, "A count question must not return a revenue answer"


def test_customers_in_arrears_is_not_treated_as_a_plain_count():
    graph = build_financial_analytics_graph(provider=DeterministicMockLLMProvider())
    resp = graph.invoke({"question": "How many customers are in arrears?", "environment": "dev"})[
        "final_response"
    ]
    assert resp.model_used == "fct_fee_assessments"
    assert "46" in resp.answer
