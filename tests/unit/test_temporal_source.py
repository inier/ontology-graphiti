import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


class TestTemporalSource:
    def _make_source(self, gm_mock=None):
        from odap.infra.query.sources.temporal_source import TemporalSource
        source = TemporalSource.__new__(TemporalSource)
        if gm_mock is None:
            gm_mock = MagicMock()
        source._graph_manager = gm_mock
        return source

    def test_query_delegates_to_graph_manager(self):
        gm = MagicMock()
        gm.query_temporal.return_value = [{"id": "1", "valid_time": "2025-01-01"}]
        source = self._make_source(gm)
        result = source.query({"valid_time": "2025-01-01", "type": "Entity"})
        gm.query_temporal.assert_called_once_with(
            valid_time="2025-01-01", transaction_time=None, entity_type="Entity"
        )
        assert len(result) == 1

    def test_query_at_time(self):
        gm = MagicMock()
        gm.query_at_valid_time.return_value = [{"id": "1"}]
        source = self._make_source(gm)
        result = source.query_at_time("2025-01-01")
        gm.query_at_valid_time.assert_called_once_with(valid_time="2025-01-01")
        assert len(result) == 1

    def test_query_history(self):
        gm = MagicMock()
        gm.get_entity_history.return_value = [{"entity_id": "e1", "timestamp": "2025-01-01"}]
        source = self._make_source(gm)
        result = source.query_history("e1")
        gm.get_entity_history.assert_called_once_with("e1")
        assert len(result) == 1

    def test_query_range(self):
        gm = MagicMock()
        gm.query_temporal.return_value = [
            {"id": "1", "valid_time": "2025-06-01"},
            {"id": "2", "valid_time": "2025-01-01"},
        ]
        source = self._make_source(gm)
        result = source.query_range("2025-03-01", "2025-12-01")
        assert len(result) == 1
        assert result[0]["id"] == "1"

    def test_query_range_empty(self):
        gm = MagicMock()
        gm.query_temporal.return_value = []
        source = self._make_source(gm)
        result = source.query_range("2025-01-01", "2025-12-01")
        assert result == []

    def test_query_with_transaction_time(self):
        gm = MagicMock()
        gm.query_temporal.return_value = [{"id": "1"}]
        source = self._make_source(gm)
        result = source.query({"transaction_time": "2025-01-01"})
        gm.query_temporal.assert_called_once_with(
            valid_time=None, transaction_time="2025-01-01", entity_type=None
        )

    def test_query_history_empty(self):
        gm = MagicMock()
        gm.get_entity_history.return_value = []
        source = self._make_source(gm)
        result = source.query_history("nonexistent")
        assert result == []

    def test_query_at_time_empty(self):
        gm = MagicMock()
        gm.query_at_valid_time.return_value = []
        source = self._make_source(gm)
        result = source.query_at_time("2099-01-01")
        assert result == []

    def test_query_range_filters_by_start_time(self):
        gm = MagicMock()
        gm.query_temporal.return_value = [
            {"id": "1", "valid_time": "2025-01-15"},
            {"id": "2", "valid_time": "2025-06-01"},
            {"id": "3", "valid_time": "2025-11-01"},
        ]
        source = self._make_source(gm)
        result = source.query_range("2025-05-01", "2025-12-01")
        assert len(result) == 2

    def test_query_with_entity_type(self):
        gm = MagicMock()
        gm.query_temporal.return_value = []
        source = self._make_source(gm)
        source.query({"type": "MilitaryUnit", "valid_time": "2025-01-01"})
        gm.query_temporal.assert_called_once_with(
            valid_time="2025-01-01", transaction_time=None, entity_type="MilitaryUnit"
        )


class TestTemporalProtocol:
    def test_temporal_source_satisfies_protocol(self):
        from odap.infra.query.protocols import TemporalSource as TemporalSourceProtocol
        from odap.infra.query.sources.temporal_source import TemporalSource
        source = TemporalSource.__new__(TemporalSource)
        source._graph_manager = MagicMock()
        assert isinstance(source, TemporalSourceProtocol)
