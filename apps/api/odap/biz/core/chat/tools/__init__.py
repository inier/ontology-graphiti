"""Tool registry — 16 BaseTool subclasses + QARetrieverTool.

Re-exports tools from the canonical location at
odap.biz.core.assistant.plugins.ai_assistant.tools — canonical source of
truth until Phase C migration is complete.

新增（ADR-051）:
- QARetrieverTool — QA RAG pipeline 工具化
"""

from odap.biz.core.assistant.plugins.ai_assistant.tools import (
    ALL_TOOLS,
    EntityListTool, EntitySearchTool, RelationQueryTool, TemporalQueryTool,
    GetOntologyContextTool, SuggestPropertiesTool, SuggestRelationsTool,
    CheckCompletenessTool,
    AddPropertyTool, UpdatePropertyTool, RemovePropertyTool,
    CreateObjectTypeTool, DeleteObjectTypeTool,
    CreateLinkTypeTool, DeleteLinkTypeTool,
    AddPropertiesBatchTool,
)

from odap.biz.core.assistant.plugins.ai_assistant.registry import (
    TOOL_REGISTRY,
    get_tools_for_llm,
    execute_tool_async,
    execute_tool,
    get_ontology_context,
    get_tool_registry,
)

# ADR-051: QA Retriever Tool (new)
from odap.biz.core.chat.tools.qa_retriever_tool import (
    QARetrieverTool,
    QARetrieverInput,
    get_qa_retriever_tool,
)

# Extended tool list including QA retriever
ALL_TOOLS_EXTENDED = list(ALL_TOOLS) + [get_qa_retriever_tool()]

__all__ = [
    "ALL_TOOLS",
    "ALL_TOOLS_EXTENDED",
    "TOOL_REGISTRY",
    "get_tools_for_llm",
    "execute_tool_async",
    "execute_tool",
    "get_ontology_context",
    "get_tool_registry",
    "QARetrieverTool",
    "QARetrieverInput",
    "get_qa_retriever_tool",
]
