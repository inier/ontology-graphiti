"""DualChannelWriter unit tests.

Covers:
- write with entities and relations: Channel A writes, Channel B episode
- Channel B failure does not affect Channel A result
- write with empty doc returns error
- write with no entities/relations returns error
- write with entities only (no relations)

Rules (AGENTS.md):
- Mock external services (GraphWriteProxy, GraphManager) but NOT storage layer
- Use pytest.mark.asyncio for async tests
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from odap.biz.data.hyper_extract.impl.dual_channel_writer import DualChannelWriter


def _mock_write_proxy():
    """Factory for a mock GraphWriteProxy."""
    proxy = MagicMock()
    proxy.add_entity.return_value = {"status": "success"}
    proxy.add_relationship.return_value = {"status": "success"}
    return proxy


def _mock_graph_manager():
    """Factory for a mock GraphManager."""
    gm = MagicMock()
    gm.add_episode = AsyncMock(return_value=None)
    return gm


class TestDualChannelWriter:
    """Tests for DualChannelWriter with mocked external services.

    Uses direct attribute injection on the writer instance to avoid
    patching lazy imports inside property methods.
    """

    @pytest.mark.asyncio
    async def test_write_entities_and_relations(self):
        """Write doc with entities and relations returns correct counts."""
        mock_proxy = _mock_write_proxy()
        mock_gm = _mock_graph_manager()

        writer = DualChannelWriter()
        writer._write_proxy = mock_proxy
        writer._graph_manager = mock_gm

        doc = {
            "entities": [
                {
                    "entity_id": "e1",
                    "entity_type": "Org",
                    "name": "中国",
                    "basic_properties": {},
                    "statistical_properties": {},
                    "capabilities": {},
                    "constraints": {},
                },
            ],
            "relations": [
                {
                    "source": "e1",
                    "target": "e2",
                    "relation_type": "owns",
                    "properties": {},
                },
            ],
        }
        result = await writer.write(doc, workspace_id="ws-1")
        assert result["status"] == "ok"
        assert result["entities_written"] == 1
        assert result["relations_written"] == 1
        mock_proxy.add_entity.assert_called_once()
        mock_proxy.add_relationship.assert_called_once()
        mock_gm.add_episode.assert_called_once()

    @pytest.mark.asyncio
    async def test_channel_b_failure_does_not_affect_channel_a(self):
        """Channel B (GraphManager) failure does not affect Channel A result."""
        mock_proxy = _mock_write_proxy()
        mock_gm = _mock_graph_manager()
        mock_gm.add_episode = AsyncMock(side_effect=Exception("Graphiti error"))

        writer = DualChannelWriter()
        writer._write_proxy = mock_proxy
        writer._graph_manager = mock_gm

        doc = {
            "entities": [
                {
                    "entity_id": "e1",
                    "entity_type": "Org",
                    "name": "中国",
                    "basic_properties": {},
                    "statistical_properties": {},
                    "capabilities": {},
                    "constraints": {},
                },
            ],
            "relations": [],
        }
        result = await writer.write(doc, workspace_id="ws-1")
        assert result["status"] == "ok"
        assert result["entities_written"] == 1
        mock_proxy.add_entity.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_empty_doc(self):
        """Write empty doc returns error."""
        writer = DualChannelWriter()
        result = await writer.write({}, workspace_id="ws-1")
        assert result.get("status") == "error"

    @pytest.mark.asyncio
    async def test_write_no_entities(self):
        """Write doc with empty entities and relations returns error."""
        writer = DualChannelWriter()
        result = await writer.write(
            {"entities": [], "relations": []}, workspace_id="ws-1"
        )
        assert result.get("status") == "error"

    @pytest.mark.asyncio
    async def test_write_entities_only(self):
        """Write doc with entities but no relations returns correct counts."""
        mock_proxy = _mock_write_proxy()
        mock_gm = _mock_graph_manager()

        writer = DualChannelWriter()
        writer._write_proxy = mock_proxy
        writer._graph_manager = mock_gm

        doc = {
            "entities": [
                {
                    "entity_id": "e1",
                    "entity_type": "Org",
                    "name": "中国",
                    "basic_properties": {},
                    "statistical_properties": {},
                    "capabilities": {},
                    "constraints": {},
                },
                {
                    "entity_id": "e2",
                    "entity_type": "Satellite",
                    "name": "北斗",
                    "basic_properties": {},
                    "statistical_properties": {},
                    "capabilities": {},
                    "constraints": {},
                },
            ],
            "relations": [],
        }
        result = await writer.write(doc, workspace_id="ws-1")
        assert result["status"] == "ok"
        assert result["entities_written"] == 2
        assert result["relations_written"] == 0
