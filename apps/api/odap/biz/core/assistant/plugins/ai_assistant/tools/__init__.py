"""AI Assistant Plugin — tool package root.

Exports all BaseTool subclasses for auto-discovery by OpenHarness PluginLoader.
"""

from odap.biz.core.assistant.plugins.ai_assistant.tools.query_tools import (
    EntityListTool,
    EntitySearchTool,
    RelationQueryTool,
    TemporalQueryTool,
)
from odap.biz.core.assistant.plugins.ai_assistant.tools.design_tools import (
    GetOntologyContextTool,
    SuggestPropertiesTool,
    SuggestRelationsTool,
    CheckCompletenessTool,
)
from odap.biz.core.assistant.plugins.ai_assistant.tools.write_tools import (
    AddPropertyTool,
    UpdatePropertyTool,
    RemovePropertyTool,
    CreateObjectTypeTool,
    DeleteObjectTypeTool,
    CreateLinkTypeTool,
    DeleteLinkTypeTool,
    AddPropertiesBatchTool,
)

# All tools listed for explicit registration (PluginLoader also auto-discovers BaseTool subclasses)
ALL_TOOLS = [
    EntityListTool(),
    EntitySearchTool(),
    RelationQueryTool(),
    TemporalQueryTool(),
    GetOntologyContextTool(),
    SuggestPropertiesTool(),
    SuggestRelationsTool(),
    CheckCompletenessTool(),
    AddPropertyTool(),
    UpdatePropertyTool(),
    RemovePropertyTool(),
    CreateObjectTypeTool(),
    DeleteObjectTypeTool(),
    CreateLinkTypeTool(),
    DeleteLinkTypeTool(),
    AddPropertiesBatchTool(),
]

__all__ = [
    "EntityListTool",
    "EntitySearchTool",
    "RelationQueryTool",
    "TemporalQueryTool",
    "GetOntologyContextTool",
    "SuggestPropertiesTool",
    "SuggestRelationsTool",
    "CheckCompletenessTool",
    "AddPropertyTool",
    "UpdatePropertyTool",
    "RemovePropertyTool",
    "CreateObjectTypeTool",
    "DeleteObjectTypeTool",
    "CreateLinkTypeTool",
    "DeleteLinkTypeTool",
    "AddPropertiesBatchTool",
    "ALL_TOOLS",
]
