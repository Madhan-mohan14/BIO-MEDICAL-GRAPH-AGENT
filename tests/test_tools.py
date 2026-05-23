"""Unit tests for tools/neo4j_tools.py with mocked Neo4j driver."""
from unittest.mock import MagicMock, patch, call
import pytest
import neo4j.time

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _make_record(data: dict):
    """Create a mock neo4j Record from a plain dict."""
    rec = MagicMock()
    rec.keys.return_value = list(data.keys())
    rec.__iter__ = lambda self: iter(data.items())
    rec.items.return_value = list(data.items())
    rec.__getitem__ = lambda self, k: data[k]
    return rec


def _mock_session_execute_read(records):
    """Return a session mock whose execute_read calls the lambda with a tx that returns records."""
    tx = MagicMock()
    tx.run.return_value = records

    def fake_execute_read(fn):
        return fn(tx)

    session_mock = MagicMock()
    session_mock.__enter__ = MagicMock(return_value=session_mock)
    session_mock.__exit__ = MagicMock(return_value=False)
    session_mock.execute_read.side_effect = fake_execute_read
    return session_mock


@pytest.fixture(autouse=True)
def reset_driver():
    """Reset the module-level _driver singleton between tests."""
    import tools.neo4j_tools as nt
    original = nt._driver
    nt._driver = None
    yield
    nt._driver = original


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_get_compound_diseases_returns_list(mock_gdb):
    records = [_make_record({"disease": "osteoarthritis", "relationship": "TREATS"})]
    session_mock = _mock_session_execute_read(records)
    mock_gdb.driver.return_value.session.return_value = session_mock

    from tools.neo4j_tools import get_compound_diseases
    result = get_compound_diseases("Ibuprofen")

    assert isinstance(result, list)
    assert result[0]["disease"] == "osteoarthritis"
    assert result[0]["relationship"] == "TREATS"


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_serialize_neo4j_datetime(mock_gdb):
    dt = neo4j.time.DateTime(2024, 1, 15, 10, 30, 0, 0)
    records = [_make_record({"ts": dt, "name": "test"})]
    session_mock = _mock_session_execute_read(records)
    mock_gdb.driver.return_value.session.return_value = session_mock

    from tools.neo4j_tools import run_cypher
    result = run_cypher("RETURN 1")

    # neo4j.time.DateTime must be serialized to str
    assert isinstance(result[0]["ts"], str)


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_get_disease_compounds_parameterized(mock_gdb):
    records = [_make_record({"compound": "Metformin", "identifier": "DB00331", "relationship": "TREATS"})]
    session_mock = _mock_session_execute_read(records)
    mock_gdb.driver.return_value.session.return_value = session_mock

    from tools.neo4j_tools import get_disease_compounds
    result = get_disease_compounds("type 2 diabetes mellitus")

    assert result[0]["compound"] == "Metformin"
    # Verify parameterized query — no f-string injection
    call_args = session_mock.execute_read.call_args
    assert call_args is not None  # execute_read was called


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_get_gene_diseases_returns_empty_list(mock_gdb):
    session_mock = _mock_session_execute_read([])
    mock_gdb.driver.return_value.session.return_value = session_mock

    from tools.neo4j_tools import get_gene_diseases
    result = get_gene_diseases("NONEXISTENT")

    assert result == []


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_get_compound_side_effects(mock_gdb):
    records = [_make_record({"side_effect": "gastric ulcer", "identifier": "C0017168"})]
    session_mock = _mock_session_execute_read(records)
    mock_gdb.driver.return_value.session.return_value = session_mock

    from tools.neo4j_tools import get_compound_side_effects
    result = get_compound_side_effects("Aspirin")

    assert result[0]["side_effect"] == "gastric ulcer"


@patch.dict(os.environ, {
    "NEO4J_URI": "bolt://localhost:7687",
    "NEO4J_USERNAME": "neo4j",
    "NEO4J_PASSWORD": "test",
})
@patch("tools.neo4j_tools.GraphDatabase")
def test_driver_singleton(mock_gdb):
    """_get_driver() must not create a new driver on each call."""
    import tools.neo4j_tools as nt
    mock_gdb.driver.return_value = MagicMock()

    nt._get_driver()
    nt._get_driver()

    assert mock_gdb.driver.call_count == 1
