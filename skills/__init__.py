"""
技能包初始化文件
实现技能的自动注册机制
"""

# 全局技能目录
SKILL_CATALOG = {}

def register_skill(name, description, handler):
    """
    注册技能

    Args:
        name: 技能名称
        description: 技能描述
        handler: 技能处理函数
    """
    SKILL_CATALOG[name] = {
        "description": description,
        "handler": handler
    }
    print(f"技能注册成功: {name} - {description}")

# 导入技能模块
# 这会触发各个模块中的register_skill()函数调用
from . import intelligence
from . import operations
from . import analysis
from . import recommendation
from . import task_management
from . import ontology_management
from . import policy
from . import computation
from . import visualization_skill
from . import planning