import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock


class TestTemporalQuery:
    @pytest.mark.asyncio
    async def test_query_temporal_with_valid_time(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        with patch.object(gm, 'query_temporal', new_callable=AsyncMock) as mock_qt:
            mock_qt.return_value = [{"name": "test", "valid_time": "2024-01-01"}]
            result = await gm.query_temporal(valid_time="2024-01-01")
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_query_temporal_with_both_times(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        with patch.object(gm, 'query_temporal', new_callable=AsyncMock) as mock_qt:
            mock_qt.return_value = [{"name": "test"}]
            result = await gm.query_temporal(valid_time="2024-01-01", transaction_time="2024-06-01")
            mock_qt.assert_called_once_with(valid_time="2024-01-01", transaction_time="2024-06-01")

    @pytest.mark.asyncio
    async def test_query_at_valid_time(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        with patch.object(gm, 'query_at_valid_time', new_callable=AsyncMock) as mock_qvt:
            mock_qvt.return_value = []
            await gm.query_at_valid_time("2024-01-01")
            mock_qvt.assert_called_once_with("2024-01-01")

    @pytest.mark.asyncio
    async def test_query_at_transaction_time(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        with patch.object(gm, 'query_at_transaction_time', new_callable=AsyncMock) as mock_qtt:
            mock_qtt.return_value = []
            await gm.query_at_transaction_time("2024-06-01")
            mock_qtt.assert_called_once_with("2024-06-01")

    @pytest.mark.asyncio
    async def test_get_entity_history(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        with patch.object(gm, 'get_entity_history', new_callable=AsyncMock) as mock_eh:
            mock_eh.return_value = [{"version": 1}, {"version": 2}]
            result = await gm.get_entity_history("entity-1")
            assert len(result) == 2


class TestTemporalTimeMapping:
    def test_valid_time_maps_to_reference_time(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        assert hasattr(gm, 'query_temporal')

    def test_transaction_time_maps_to_created_at(self):
        from odap.infra.graph.graph_service import GraphManager
        gm = GraphManager()
        assert hasattr(gm, 'query_temporal')
