"""
L3 Application — 本体应用层

ADR-068 中的 L3 领域层。负责所有面向用户和外部系统的交互:
  - chat/          统一 AI 助手 (三合一入口)
  - intent/        意图识别 (从 cognition/ 迁移)
  - navigation/    知识导航 (从 cognition/ 迁移)
  - explanation/   解释引擎 (从 cognition/ 迁移)
  - thought_graph/ 思维图谱 (从 cognition/ 迁移)
  - oms/           对象元数据服务 (只读缓存)
  - runtime/       运行时引擎 (World State / 状态机)
  - servitization/ API 服务化部署
  - query_api/     NL 查询 API
  - team_agent/    团队智能体协同
  - abution_graph/ 属性图引擎
  - harness/       数据集成编排

通过 DesignContract / BuildResultContract / ReasoningServiceContract
调用下层能力。
"""

__all__ = []
