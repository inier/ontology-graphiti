"""Action Type 模块 - 业务接口层 (FR-034)

设计原则：
- Action Type = 业务接口 (面向业务用户)
- Skill = 工程实现 (如何执行)
- 通过 linked_skill_id 建立 Action → Skill 的委托关系
- 调用 Action → 查找 linked_skill → 调用 Skill → 记录 ActionExecution
- 调用前 OPA 权限校验 (write-time check)
- 调用后写入审计日志
"""
