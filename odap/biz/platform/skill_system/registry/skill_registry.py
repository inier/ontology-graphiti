"""工具注册表"""

from typing import Dict, Any, List, Optional, Callable


class ToolInfo:
    """工具信息"""
    
    def __init__(self, name: str, description: str = "", 
                 parameters: Dict[str, Any] = None, 
                 handler: Callable = None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}
        self.handler = handler
        self.metadata: Dict[str, Any] = {}


class SkillRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
    
    def register(self, name: str, handler: Callable, 
                description: str = "", 
                parameters: Dict[str, Any] = None) -> bool:
        """注册工具
        
        Args:
            name: 工具名称
            handler: 处理函数
            description: 描述
            parameters: 参数定义
            
        Returns:
            是否注册成功
        """
        tool = ToolInfo(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler
        )
        self._tools[name] = tool
        return True
    
    def unregister(self, name: str) -> bool:
        """取消注册
        
        Args:
            name: 工具名称
            
        Returns:
            是否取消注册成功
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具信息
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出工具
        
        Returns:
            工具列表
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
            for tool in self._tools.values()
        ]
    
    def invoke(self, name: str, parameters: Dict[str, Any] = None) -> Any:
        """调用工具
        
        Args:
            name: 工具名称
            parameters: 参数
            
        Returns:
            调用结果
        """
        tool = self._tools.get(name)
        if not tool or not tool.handler:
            raise ValueError(f"Tool {name} not found or not callable")
        
        return tool.handler(**(parameters or {}))
    
    def is_registered(self, name: str) -> bool:
        """检查是否已注册
        
        Args:
            name: 工具名称
            
        Returns:
            是否已注册
        """
        return name in self._tools
