"""决策管道接口定义

定义决策管道各组件的抽象接口，实现依赖倒置
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class AnalysisResultInterface(ABC):
    """分析结果接口"""

    @property
    @abstractmethod
    def summary(self) -> str:
        """获取分析摘要"""
        pass

    @property
    @abstractmethod
    def entities(self) -> List[Dict[str, Any]]:
        """获取识别的实体列表"""
        pass

    @property
    @abstractmethod
    def patterns(self) -> List[str]:
        """获取识别的模式列表"""
        pass

    @property
    @abstractmethod
    def risks(self) -> List[str]:
        """获取风险列表"""
        pass

    @property
    @abstractmethod
    def confidence(self) -> float:
        """获取置信度"""
        pass


class DecisionOptionInterface(ABC):
    """决策选项接口"""

    @property
    @abstractmethod
    def option_id(self) -> str:
        """选项ID"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """选项名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """选项描述"""
        pass

    @property
    @abstractmethod
    def risk_level(self) -> str:
        """风险等级: low, medium, high"""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """优先级"""
        pass


class DecisionResultInterface(ABC):
    """决策结果接口"""

    @property
    @abstractmethod
    def decision_id(self) -> str:
        """决策ID"""
        pass

    @property
    @abstractmethod
    def recommended_option(self) -> Optional[DecisionOptionInterface]:
        """推荐的选项"""
        pass

    @property
    @abstractmethod
    def alternative_options(self) -> List[DecisionOptionInterface]:
        """备选选项列表"""
        pass

    @property
    @abstractmethod
    def reasoning(self) -> str:
        """决策推理过程"""
        pass

    @property
    @abstractmethod
    def confidence(self) -> float:
        """决策置信度"""
        pass


class ValidationResultInterface(ABC):
    """验证结果接口"""

    @property
    @abstractmethod
    def is_valid(self) -> bool:
        """验证是否通过"""
        pass

    @property
    @abstractmethod
    def validation_details(self) -> Dict[str, Any]:
        """验证详情"""
        pass

    @property
    @abstractmethod
    def errors(self) -> List[str]:
        """验证错误列表"""
        pass


class SemanticRetrieverInterface(ABC):
    """语义检索器接口"""

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 10) -> Any:
        """检索相关内容

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果
        """
        pass


class DecisionEngineInterface(ABC):
    """决策引擎接口"""

    @abstractmethod
    def recommend(self, request: Any) -> Any:
        """生成决策推荐

        Args:
            request: 推荐请求

        Returns:
            推荐结果
        """
        pass


class PolicyValidatorInterface(ABC):
    """策略验证器接口"""

    @abstractmethod
    def check_permission(
        self,
        user: str,
        action: str,
        resource: str,
        environment: Dict[str, Any]
    ) -> Dict[str, Any]:
        """检查权限

        Args:
            user: 用户标识
            action: 操作类型
            resource: 资源标识
            environment: 环境参数

        Returns:
            验证结果，包含 allow 字段
        """
        pass


class ActionExecutorInterface(ABC):
    """动作执行器接口"""

    @abstractmethod
    async def submit_action(self, action_request: Any) -> Dict[str, Any]:
        """提交动作执行

        Args:
            action_request: 动作请求

        Returns:
            动作执行记录
        """
        pass

    @abstractmethod
    async def get_action_status(self, action_id: str) -> Dict[str, Any]:
        """获取动作执行状态

        Args:
            action_id: 动作ID

        Returns:
            动作状态信息
        """
        pass


class FeedbackLoopInterface(ABC):
    """反馈循环接口"""

    @abstractmethod
    async def close_loop(self, action_record: Dict[str, Any]) -> Dict[str, Any]:
        """关闭反馈循环

        Args:
            action_record: 动作执行记录

        Returns:
            反馈结果
        """
        pass


class DecisionPipelineInterface(ABC):
    """决策管道接口

    定义决策管道的行为规范，支持以下阶段：
    1. Analyze - 分析输入，理解问题
    2. Decide - 生成决策选项
    3. Validate - 验证决策是否符合策略
    4. Perform - 执行决策
    5. Feedback - 收集反馈
    """

    @abstractmethod
    async def execute(self, input_data: Any) -> Any:
        """执行完整的决策管道

        Args:
            input_data: 输入数据

        Returns:
            管道执行结果
        """
        pass

    @property
    @abstractmethod
    def semantic_retriever(self) -> SemanticRetrieverInterface:
        """获取语义检索器"""
        pass

    @property
    @abstractmethod
    def decision_engine(self) -> DecisionEngineInterface:
        """获取决策引擎"""
        pass

    @property
    @abstractmethod
    def policy_validator(self) -> PolicyValidatorInterface:
        """获取策略验证器"""
        pass

    @property
    @abstractmethod
    def action_executor(self) -> ActionExecutorInterface:
        """获取动作执行器"""
        pass

    @property
    @abstractmethod
    def feedback_loop(self) -> FeedbackLoopInterface:
        """获取反馈循环"""
        pass
