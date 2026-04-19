# 用户认知引擎模块设计文档

> **优先级**: P0 | **相关 ADR**: ADR-038, ADR-049

## 1. 模块概述

### 1.1 模块定位

`user_cognition_engine` 是 ODAP 平台的核心引擎之一，负责理解用户意图、提供知识导航、生成可解释的决策过程，并为不同角色提供定制化的视图。它是连接用户与系统的桥梁，提升用户体验和系统透明度。

### 1.2 核心职责

| 职责 | 描述 |
|------|------|
| 意图识别 | 解析用户问题，识别用户角色和意图 |
| 知识导航 | 基于本体的知识检索，路径追踪 |
| 解释引擎 | 生成决策过程解释，可视化推理链 |
| 角色视图 | 管理不同角色的界面展示和权限 |
| 交互管理 | 处理用户交互，提供个性化反馈 |

---

## 2. 架构设计

### 2.1 模块架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       用户认知引擎 (UserCognitionEngine)                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐    ┌───────────────┐  │
│  │  意图识别器   │    │  知识导航器   │    │   解释引擎   │    │  角色视图管理器 │  │
│  │  IntentRecognizer│  │ KnowledgeNavigator│  │ ExplanationEngine│  │ RoleViewManager│  │
│  └───────────────┘    └───────────────┘    └───────────────┘    └───────────────┘  │
│         │                      │                      │                      │        │
│         └──────────────────────┼──────────────────────┼──────────────────────┘        │
│                                ▼                                                  │
│                        ┌───────────────┐                                           │
│                        │  交互管理器   │                                           │
│                        │ InteractionManager│                                       │
│                        └───────────────┘                                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

| 组件 | 职责 | 接口 | 依赖 |
|------|------|------|------|
| **意图识别器** | 解析用户问题，识别角色 | `recognizeIntent()` | NLP |
| **知识导航器** | 基于本体的知识检索 | `navigateKnowledge()` | Graphiti |
| **解释引擎** | 生成决策过程解释 | `explainDecision()` | 推理链 |
| **角色视图管理器** | 管理角色界面 | `getRoleView()` | 权限 |
| **交互管理器** | 处理用户交互 | `manageInteraction()` | 前端 |

---

## 3. 核心数据模型

### 3.1 意图识别模型

```python
# user_cognition_engine/models/intent.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class UserRole(str, Enum):
    """用户角色"""
    COMMANDER = "commander"
    ADMIN = "admin"
    ANALYST = "analyst"
    OPERATOR = "operator"
    GUEST = "guest"

class IntentType(str, Enum):
    """意图类型"""
    QUESTION = "question"
    ANALYSIS = "analysis"
    DECISION = "decision"
    OPERATION = "operation"
    CONFIG = "config"

class IntentResult(BaseModel):
    """意图识别结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_text: str
    role: UserRole
    intent: IntentType
    confidence: float = Field(ge=0, le=1)
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    processing_time: float = 0.0

class IntentHistory(BaseModel):
    """意图历史"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    intent_result: IntentResult
    response: Dict[str, Any] = Field(default_factory=dict)
    feedback: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.now)
```

### 3.2 知识导航模型

```python
# user_cognition_engine/models/navigation.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class NavigationType(str, Enum):
    """导航类型"""
    DIRECT = "direct"
    HIERARCHICAL = "hierarchical"
    SEMANTIC = "semantic"
    TEMPORAL = "temporal"

class NavigationNode(BaseModel):
    """导航节点"""
    id: str
    type: str
    name: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    score: float = 0.0

class NavigationEdge(BaseModel):
    """导航边"""
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0

class NavigationPath(BaseModel):
    """导航路径"""
    nodes: List[NavigationNode] = Field(default_factory=list)
    edges: List[NavigationEdge] = Field(default_factory=list)
    score: float = 0.0
    length: int = 0

class NavigationResult(BaseModel):
    """导航结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    navigation_type: NavigationType
    paths: List[NavigationPath] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    processing_time: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)

class NavigationContext(BaseModel):
    """导航上下文"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    recent_queries: List[str] = Field(default_factory=list)
    navigation_history: List[str] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
```

### 3.3 解释引擎模型

```python
# user_cognition_engine/models/explanation.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class ExplanationType(str, Enum):
    """解释类型"""
    DECISION = "decision"
    RECOMMENDATION = "recommendation"
    PREDICTION = "prediction"
    ERROR = "error"

class ExplanationStep(BaseModel):
    """解释步骤"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    step_number: int
    description: str
    input: Dict[str, Any] = Field(default_factory=dict)
    output: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.now)

class ExplanationResult(BaseModel):
    """解释结果"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str
    explanation_type: ExplanationType
    steps: List[ExplanationStep] = Field(default_factory=list)
    summary: str = ""
    visualization_data: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    processing_time: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)

class ExplanationFeedback(BaseModel):
    """解释反馈"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    explanation_id: str
    user_id: str
    helpfulness: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    completeness: int = Field(ge=1, le=5)
    comments: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
```

### 3.4 角色视图模型

```python
# user_cognition_engine/models/role.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class ViewType(str, Enum):
    """视图类型"""
    DASHBOARD = "dashboard"
    GRAPH = "graph"
    TIMELINE = "timeline"
    MAP = "map"
    FORM = "form"

class ViewComponent(BaseModel):
    """视图组件"""
    id: str
    type: str
    configuration: Dict[str, Any] = Field(default_factory=dict)
    visibility: bool = True
    priority: int = 0

class RoleView(BaseModel):
    """角色视图"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: UserRole
    view_type: ViewType
    components: List[ViewComponent] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=dict)
    permissions: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

class ViewConfig(BaseModel):
    """视图配置"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    role: UserRole
    view_preferences: Dict[str, Any] = Field(default_factory=dict)
    customizations: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
```

### 3.5 交互管理模型

```python
# user_cognition_engine/models/interaction.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class InteractionType(str, Enum):
    """交互类型"""
    QUERY = "query"
    FEEDBACK = "feedback"
    NAVIGATION = "navigation"
    ACTION = "action"
    ERROR = "error"

class InteractionState(str, Enum):
    """交互状态"""
    STARTED = "started"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Interaction(BaseModel):
    """交互"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    type: InteractionType
    state: InteractionState = InteractionState.STARTED
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None

class Session(BaseModel):
    """会话"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    started_at: datetime = Field(default_factory=datetime.now)
    last_interaction: Optional[datetime] = None
    interactions: List[str] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
```

---

## 4. 核心接口设计

### 4.1 意图识别器接口

```python
# user_cognition_engine/interfaces/intent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IIntentRecognizer(ABC):
    """意图识别器接口"""
    
    @abstractmethod
    async def recognize_intent(
        self, 
        input_text: str, 
        role: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """识别意图"""
        pass
    
    @abstractmethod
    async def get_intent_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取意图历史"""
        pass
    
    @abstractmethod
    async def update_intent_model(self) -> bool:
        """更新意图模型"""
        pass
```

### 4.2 知识导航器接口

```python
# user_cognition_engine/interfaces/navigation.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IKnowledgeNavigator(ABC):
    """知识导航器接口"""
    
    @abstractmethod
    async def navigate_knowledge(
        self, 
        query: str, 
        navigation_type: str = "semantic",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """导航知识"""
        pass
    
    @abstractmethod
    async def get_navigation_context(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """获取导航上下文"""
        pass
    
    @abstractmethod
    async def update_navigation_context(
        self, 
        user_id: str, 
        context: Dict[str, Any]
    ) -> bool:
        """更新导航上下文"""
        pass
```

### 4.3 解释引擎接口

```python
# user_cognition_engine/interfaces/explanation.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IExplanationEngine(ABC):
    """解释引擎接口"""
    
    @abstractmethod
    async def explain_decision(
        self, 
        decision_id: str, 
        explanation_type: str = "decision"
    ) -> Dict[str, Any]:
        """解释决策"""
        pass
    
    @abstractmethod
    async def get_explanation(
        self, 
        explanation_id: str
    ) -> Dict[str, Any]:
        """获取解释"""
        pass
    
    @abstractmethod
    async def add_explanation_feedback(
        self, 
        feedback: Dict[str, Any]
    ) -> str:
        """添加解释反馈"""
        pass
```

### 4.4 角色视图管理器接口

```python
# user_cognition_engine/interfaces/role.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IRoleViewManager(ABC):
    """角色视图管理器接口"""
    
    @abstractmethod
    async def get_role_view(
        self, 
        role: str, 
        view_type: str = "dashboard"
    ) -> Dict[str, Any]:
        """获取角色视图"""
        pass
    
    @abstractmethod
    async def update_role_view(
        self, 
        role: str, 
        view_config: Dict[str, Any]
    ) -> bool:
        """更新角色视图"""
        pass
    
    @abstractmethod
    async def get_user_view_config(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """获取用户视图配置"""
        pass
```

### 4.5 交互管理器接口

```python
# user_cognition_engine/interfaces/interaction.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IInteractionManager(ABC):
    """交互管理器接口"""
    
    @abstractmethod
    async def manage_interaction(
        self, 
        user_id: str, 
        interaction_type: str, 
        input_data: Dict[str, Any]
    ) -> str:
        """管理交互"""
        pass
    
    @abstractmethod
    async def get_interaction(
        self, 
        interaction_id: str
    ) -> Dict[str, Any]:
        """获取交互"""
        pass
    
    @abstractmethod
    async def get_session(
        self, 
        session_id: str
    ) -> Dict[str, Any]:
        """获取会话"""
        pass
    
    @abstractmethod
    async def end_session(
        self, 
        session_id: str
    ) -> bool:
        """结束会话"""
        pass
```

---

## 5. 实现类设计

### 5.1 意图识别器实现

```python
# user_cognition_engine/impl/intent.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.intent import (
    IntentResult, IntentHistory, UserRole, IntentType
)
from .interfaces.intent import IIntentRecognizer

class IntentRecognizer(IIntentRecognizer):
    """意图识别器实现"""
    
    def __init__(self, nlp_service, storage):
        self.nlp_service = nlp_service
        self.storage = storage
    
    async def recognize_intent(
        self, 
        input_text: str, 
        role: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """识别意图"""
        # 调用NLP服务进行意图识别
        nlp_result = await self.nlp_service.analyze(
            input_text, 
            context=context or {}
        )
        
        # 构建意图结果
        intent_result = IntentResult(
            input_text=input_text,
            role=UserRole(role),
            intent=IntentType(nlp_result.get('intent', 'question')),
            confidence=nlp_result.get('confidence', 0.5),
            entities=nlp_result.get('entities', []),
            context=context or {}
        )
        
        # 保存意图结果
        await self.storage.save_intent_result(intent_result.model_dump())
        
        return intent_result.model_dump()
    
    async def get_intent_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取意图历史"""
        return await self.storage.get_intent_history(user_id, limit)
    
    async def update_intent_model(self) -> bool:
        """更新意图模型"""
        # 实现模型更新逻辑
        return True
```

### 5.2 知识导航器实现

```python
# user_cognition_engine/impl/navigation.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.navigation import (
    NavigationResult, NavigationPath, NavigationNode, 
    NavigationEdge, NavigationType, NavigationContext
)
from .interfaces.navigation import IKnowledgeNavigator

class KnowledgeNavigator(IKnowledgeNavigator):
    """知识导航器实现"""
    
    def __init__(self, graphiti_client, storage):
        self.graphiti = graphiti_client
        self.storage = storage
    
    async def navigate_knowledge(
        self, 
        query: str, 
        navigation_type: str = "semantic",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """导航知识"""
        # 调用Graphiti进行知识检索
        search_result = await self.graphiti.search_episodes(
            query=query,
            categories=context.get('categories', []) if context else []
        )
        
        # 构建导航结果
        nodes = []
        edges = []
        
        for episode in search_result:
            node = NavigationNode(
                id=episode.get('id'),
                type=episode.get('type'),
                name=episode.get('name'),
                properties=episode.get('properties', {}),
                score=episode.get('score', 0.0)
            )
            nodes.append(node)
        
        # 构建导航路径
        paths = []
        if nodes:
            path = NavigationPath(
                nodes=nodes,
                edges=edges,
                score=sum(n.score for n in nodes) / len(nodes),
                length=len(nodes)
            )
            paths.append(path)
        
        result = NavigationResult(
            query=query,
            navigation_type=NavigationType(navigation_type),
            paths=paths,
            total_nodes=len(nodes),
            total_edges=len(edges)
        )
        
        return result.model_dump()
    
    async def get_navigation_context(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """获取导航上下文"""
        return await self.storage.get_navigation_context(user_id)
    
    async def update_navigation_context(
        self, 
        user_id: str, 
        context: Dict[str, Any]
    ) -> bool:
        """更新导航上下文"""
        navigation_context = NavigationContext(
            user_id=user_id,
            session_id=context.get('session_id', ''),
            recent_queries=context.get('recent_queries', []),
            navigation_history=context.get('navigation_history', []),
            preferences=context.get('preferences', {})
        )
        
        await self.storage.save_navigation_context(navigation_context.model_dump())
        return True
```

### 5.3 解释引擎实现

```python
# user_cognition_engine/impl/explanation.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.explanation import (
    ExplanationResult, ExplanationStep, ExplanationType,
    ExplanationFeedback
)
from .interfaces.explanation import IExplanationEngine

class ExplanationEngine(IExplanationEngine):
    """解释引擎实现"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def explain_decision(
        self, 
        decision_id: str, 
        explanation_type: str = "decision"
    ) -> Dict[str, Any]:
        """解释决策"""
        # 获取决策数据
        decision = await self.storage.get_decision(decision_id)
        if not decision:
            raise ValueError(f"Decision {decision_id} not found")
        
        # 构建解释步骤
        steps = []
        
        # 步骤1: 问题分析
        step1 = ExplanationStep(
            step_number=1,
            description="问题分析",
            input={"question": decision.get('question', '')},
            output={"analysis": "分析用户问题，识别关键实体和关系"},
            confidence=0.95
        )
        steps.append(step1)
        
        # 步骤2: 知识检索
        step2 = ExplanationStep(
            step_number=2,
            description="知识检索",
            input={"query": decision.get('query', '')},
            output={"results": "从图谱中检索相关知识"},
            confidence=0.90
        )
        steps.append(step2)
        
        # 步骤3: 推理过程
        step3 = ExplanationStep(
            step_number=3,
            description="推理过程",
            input={"knowledge": "检索到的知识"},
            output={"reasoning": "基于知识进行推理"},
            confidence=0.85
        )
        steps.append(step3)
        
        # 步骤4: 决策生成
        step4 = ExplanationStep(
            step_number=4,
            description="决策生成",
            input={"reasoning": "推理结果"},
            output={"decision": decision.get('result', '')},
            confidence=0.80
        )
        steps.append(step4)
        
        # 构建解释结果
        result = ExplanationResult(
            decision_id=decision_id,
            explanation_type=ExplanationType(explanation_type),
            steps=steps,
            summary="基于图谱知识和推理过程生成的决策",
            visualization_data={"steps": len(steps)},
            confidence=0.85
        )
        
        # 保存解释结果
        await self.storage.save_explanation(result.model_dump())
        
        return result.model_dump()
    
    async def get_explanation(
        self, 
        explanation_id: str
    ) -> Dict[str, Any]:
        """获取解释"""
        return await self.storage.get_explanation(explanation_id)
    
    async def add_explanation_feedback(
        self, 
        feedback: Dict[str, Any]
    ) -> str:
        """添加解释反馈"""
        explanation_feedback = ExplanationFeedback(**feedback)
        feedback_id = await self.storage.save_explanation_feedback(explanation_feedback.model_dump())
        return feedback_id
```

### 5.4 角色视图管理器实现

```python
# user_cognition_engine/impl/role.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.role import (
    RoleView, ViewComponent, ViewType, UserRole, ViewConfig
)
from .interfaces.role import IRoleViewManager

class RoleViewManager(IRoleViewManager):
    """角色视图管理器实现"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def get_role_view(
        self, 
        role: str, 
        view_type: str = "dashboard"
    ) -> Dict[str, Any]:
        """获取角色视图"""
        # 从存储中获取角色视图
        role_view = await self.storage.get_role_view(role, view_type)
        
        if role_view:
            return role_view
        
        # 如果不存在，创建默认视图
        default_view = self._create_default_view(role, view_type)
        await self.storage.save_role_view(default_view.model_dump())
        
        return default_view.model_dump()
    
    async def update_role_view(
        self, 
        role: str, 
        view_config: Dict[str, Any]
    ) -> bool:
        """更新角色视图"""
        # 实现视图更新逻辑
        return await self.storage.update_role_view(role, view_config)
    
    async def get_user_view_config(
        self, 
        user_id: str
    ) -> Dict[str, Any]:
        """获取用户视图配置"""
        view_config = await self.storage.get_user_view_config(user_id)
        
        if view_config:
            return view_config
        
        # 创建默认配置
        default_config = ViewConfig(
            user_id=user_id,
            role=UserRole.GUEST,
            view_preferences={},
            customizations={}
        )
        
        await self.storage.save_user_view_config(default_config.model_dump())
        return default_config.model_dump()
    
    def _create_default_view(self, role: str, view_type: str) -> RoleView:
        """创建默认视图"""
        components = []
        
        if view_type == "dashboard":
            if role == "commander":
                components = [
                    ViewComponent(id="overview", type="overview", visibility=True),
                    ViewComponent(id="alarms", type="alarms", visibility=True),
                    ViewComponent(id="recommendations", type="recommendations", visibility=True)
                ]
            elif role == "admin":
                components = [
                    ViewComponent(id="system_status", type="system_status", visibility=True),
                    ViewComponent(id="user_management", type="user_management", visibility=True),
                    ViewComponent(id="audit_log", type="audit_log", visibility=True)
                ]
        
        return RoleView(
            role=UserRole(role),
            view_type=ViewType(view_type),
            components=components,
            layout={},
            permissions=self._get_default_permissions(role)
        )
    
    def _get_default_permissions(self, role: str) -> List[str]:
        """获取默认权限"""
        permissions = {
            "commander": ["read", "write", "execute", "admin"],
            "admin": ["read", "write", "admin"],
            "analyst": ["read", "write"],
            "operator": ["read", "execute"],
            "guest": ["read"]
        }
        return permissions.get(role, ["read"])
```

### 5.5 交互管理器实现

```python
# user_cognition_engine/impl/interaction.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from .models.interaction import (
    Interaction, Session, InteractionType, InteractionState
)
from .interfaces.interaction import IInteractionManager

class InteractionManager(IInteractionManager):
    """交互管理器实现"""
    
    def __init__(self, storage):
        self.storage = storage
    
    async def manage_interaction(
        self, 
        user_id: str, 
        interaction_type: str, 
        input_data: Dict[str, Any]
    ) -> str:
        """管理交互"""
        # 获取或创建会话
        session = await self._get_or_create_session(user_id)
        
        # 创建交互
        interaction = Interaction(
            user_id=user_id,
            session_id=session['id'],
            type=InteractionType(interaction_type),
            input_data=input_data
        )
        
        # 保存交互
        interaction_id = await self.storage.save_interaction(interaction.model_dump())
        
        # 更新会话
        session['interactions'].append(interaction_id)
        session['last_interaction'] = datetime.now().isoformat()
        await self.storage.update_session(session['id'], session)
        
        return interaction_id
    
    async def get_interaction(
        self, 
        interaction_id: str
    ) -> Dict[str, Any]:
        """获取交互"""
        return await self.storage.get_interaction(interaction_id)
    
    async def get_session(
        self, 
        session_id: str
    ) -> Dict[str, Any]:
        """获取会话"""
        return await self.storage.get_session(session_id)
    
    async def end_session(
        self, 
        session_id: str
    ) -> bool:
        """结束会话"""
        session = await self.storage.get_session(session_id)
        if not session:
            return False
        
        session['ended_at'] = datetime.now().isoformat()
        session['duration_seconds'] = (datetime.now() - datetime.fromisoformat(session['started_at'])).total_seconds()
        
        await self.storage.update_session(session_id, session)
        return True
    
    async def _get_or_create_session(self, user_id: str) -> Dict[str, Any]:
        """获取或创建会话"""
        # 查找活跃会话
        active_sessions = await self.storage.get_active_sessions(user_id)
        
        if active_sessions:
            return active_sessions[0]
        
        # 创建新会话
        session = Session(
            user_id=user_id,
            context={}
        )
        
        session_id = await self.storage.save_session(session.model_dump())
        session_data = session.model_dump()
        session_data['id'] = session_id
        
        return session_data
```

---

## 6. 目录结构

```
user_cognition_engine/
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── intent.py         # 意图识别模型
│   ├── navigation.py    # 知识导航模型
│   ├── explanation.py   # 解释引擎模型
│   ├── role.py          # 角色视图模型
│   └── interaction.py   # 交互管理模型
├── interfaces/
│   ├── __init__.py
│   ├── intent.py         # 意图识别接口
│   ├── navigation.py    # 知识导航接口
│   ├── explanation.py   # 解释引擎接口
│   ├── role.py          # 角色视图接口
│   └── interaction.py   # 交互管理接口
├── impl/
│   ├── __init__.py
│   ├── intent.py         # 意图识别实现
│   ├── navigation.py    # 知识导航实现
│   ├── explanation.py   # 解释引擎实现
│   ├── role.py          # 角色视图实现
│   └── interaction.py   # 交互管理实现
├── services/
│   ├── __init__.py
│   ├── intent_service.py      # 意图识别服务
│   ├── navigation_service.py   # 知识导航服务
│   ├── explanation_service.py  # 解释服务
│   ├── role_service.py         # 角色服务
│   └── interaction_service.py  # 交互服务
├── storage/
│   ├── __init__.py
│   ├── mongodb_storage.py   # MongoDB存储
│   └── redis_storage.py     # Redis缓存
├── api/
│   ├── __init__.py
│   ├── routes.py        # API路由
│   └── schemas.py       # API Schema
└── config.py            # 配置
```

---

## 7. API 接口设计

### 7.1 意图识别 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/cognition/intent` | POST | 识别意图 | `{"input_text": "...", "role": "commander"}` | `{"intent": "question", "confidence": 0.95}` |
| `/api/cognition/intent/history` | GET | 获取意图历史 | N/A | `[{"intent": "...", "timestamp": "..."}]` |
| `/api/cognition/intent/model` | PUT | 更新意图模型 | `{"model_version": "1.0.0"}` | `{"success": true}` |

### 7.2 知识导航 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/cognition/navigate` | POST | 导航知识 | `{"query": "...", "type": "semantic"}` | `{"paths": [...], "nodes": [...]}` |
| `/api/cognition/context` | GET | 获取导航上下文 | N/A | `{"recent_queries": [...], "preferences": {...}}` |
| `/api/cognition/context` | PUT | 更新导航上下文 | `{"recent_queries": [...], "preferences": {...}}` | `{"success": true}` |

### 7.3 解释引擎 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/cognition/explain` | POST | 解释决策 | `{"decision_id": "...", "type": "decision"}` | `{"steps": [...], "summary": "..."}` |
| `/api/cognition/explain/{id}` | GET | 获取解释 | N/A | `{"steps": [...], "visualization_data": {...}}` |
| `/api/cognition/explain/feedback` | POST | 添加解释反馈 | `{"explanation_id": "...", "helpfulness": 5}` | `{"feedback_id": "..."}` |

### 7.4 角色视图 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/cognition/view` | GET | 获取角色视图 | N/A | `{"components": [...], "layout": {...}}` |
| `/api/cognition/view` | PUT | 更新角色视图 | `{"components": [...], "layout": {...}}` | `{"success": true}` |
| `/api/cognition/view/user` | GET | 获取用户视图配置 | N/A | `{"preferences": {...}, "customizations": {...}}` |
| `/api/cognition/view/user` | PUT | 更新用户视图配置 | `{"preferences": {...}}` | `{"success": true}` |

### 7.5 交互管理 API

| 端点 | 方法 | 功能 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/cognition/interaction` | POST | 创建交互 | `{"type": "query", "input_data": {...}}` | `{"interaction_id": "..."}` |
| `/api/cognition/interaction/{id}` | GET | 获取交互 | N/A | `{"type": "...", "state": "...", "output_data": {...}}` |
| `/api/cognition/session` | GET | 获取会话 | N/A | `{"interactions": [...], "context": {...}}` |
| `/api/cognition/session` | DELETE | 结束会话 | N/A | `{"success": true, "duration": 120.5}` |

---

## 8. 集成与依赖

### 8.1 核心依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.9+ | 运行环境 |
| Pydantic | 2.0+ | 数据验证 |
| FastAPI | 0.100+ | API框架 |
| MongoDB | 6.0+ | 存储 |
| Redis | 7.0+ | 缓存 |
| Graphiti | 最新版 | 知识图谱 |
| NLP服务 | 最新版 | 意图识别 |

### 8.2 集成点

| 集成点 | 接口 | 用途 |
|---------|------|------|
| Graphiti | `graphiti_client` | 知识检索 |
| 前端 | `/api/cognition/*` | 用户界面 |
| NLP | `nlp_service` | 意图识别 |
| 安全 | `OPA` | 权限控制 |
| 决策系统 | `decision_service` | 解释决策 |

---

## 9. 部署与配置

### 9.1 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `MONGODB_URI` | str | "mongodb://localhost:27017" | MongoDB连接 |
| `REDIS_URI` | str | "redis://localhost:6379" | Redis连接 |
| `GRAPHITI_URL` | str | "http://localhost:8000" | Graphiti服务 |
| `NLP_SERVICE_URL` | str | "http://localhost:8001" | NLP服务 |
| `LOG_LEVEL` | str | "INFO" | 日志级别 |
| `SESSION_TIMEOUT` | int | 3600 | 会话超时(秒) |
| `CACHE_TTL` | int | 300 | 缓存过期(秒) |

### 9.2 部署方式

```yaml
# docker-compose.yml
version: '3.8'
services:
  user-cognition:
    image: odap-user-cognition:latest
    ports:
      - "8002:8000"
    environment:
      - MONGODB_URI=mongodb://mongodb:27017
      - REDIS_URI=redis://redis:6379
      - GRAPHITI_URL=http://graphiti:8000
      - NLP_SERVICE_URL=http://nlp:8001
    depends_on:
      - mongodb
      - redis
      - graphiti
      - nlp
```

---

## 10. 监控与告警

### 10.1 监控指标

| 指标 | 类型 | 说明 |
|------|------|------|
| `cognition_intent_recognition_time` | Histogram | 意图识别时间 |
| `cognition_navigation_time` | Histogram | 知识导航时间 |
| `cognition_explanation_time` | Histogram | 解释生成时间 |
| `cognition_interaction_count` | Counter | 交互次数 |
| `cognition_error_count` | Counter | 错误次数 |
| `cognition_session_duration` | Histogram | 会话时长 |

### 10.2 告警规则

| 规则 | 条件 | 级别 |
|------|------|------|
| 意图识别超时 | `cognition_intent_recognition_time > 2000` | 警告 |
| 知识导航失败 | `rate(cognition_error_count[5m]) > 0.1` | 严重 |
| 会话异常结束 | `cognition_session_duration < 10` | 警告 |
| 系统负载高 | `cognition_interaction_count > 100` | 警告 |

---

## 11. 测试策略

### 11.1 单元测试

| 模块 | 测试覆盖率 | 测试场景 |
|------|------------|----------|
| 意图识别器 | 90% | 不同意图类型、角色识别、上下文理解 |
| 知识导航器 | 85% | 不同导航类型、路径构建、上下文管理 |
| 解释引擎 | 95% | 不同解释类型、步骤生成、反馈处理 |
| 角色视图管理器 | 80% | 不同角色视图、权限控制、配置管理 |
| 交互管理器 | 85% | 会话管理、状态跟踪、错误处理 |

### 11.2 集成测试

| 测试场景 | 验证点 |
|----------|--------|
| 完整用户交互流程 | 意图识别 → 知识导航 → 解释生成 → 角色视图 |
| 多角色场景 | 不同角色的视图和权限控制 |
| 会话管理 | 会话创建、更新、结束的完整流程 |
| 错误处理 | 各种错误场景的处理和恢复 |

### 11.3 性能测试

| 测试指标 | 目标 |
|----------|------|
| 意图识别响应 | < 500ms (P95) |
| 知识导航响应 | < 1000ms (P95) |
| 解释生成响应 | < 2000ms (P95) |
| 并发用户数 | 支持 100+ 同时在线 |
| 会话处理 | 支持 1000+ 并发会话 |

---

## 12. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-19 | 初始版本 |
| 1.1.0 | 2026-05-01 | 增强解释引擎、添加会话管理 |

---

**相关文档**:
- [Graphiti 客户端模块设计](../graphiti_client/DESIGN.md)
- [QA 引擎模块设计](../qa_engine/DESIGN.md)
- [安全策略文档](../../security/SECURITY.md)
