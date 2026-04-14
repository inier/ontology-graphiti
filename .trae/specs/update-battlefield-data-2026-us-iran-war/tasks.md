# Tasks - 更新战场模拟数据为 2026 美伊战争场景

## Task Dependencies
所有任务依赖于 `Task 1` 的完成，因为需要使用更新后的配置。

---

- [x] Task 1: 更新 battlefield_ontology.py 配置
  - [x] SubTask 1.1: 更新 BATTLEFIELD_CONFIG 中的 factions 为 2026 美伊战争参战方
  - [x] SubTask 1.2: 更新 areas 区域描述为真实地理位置
  - [x] SubTask 1.3: 更新 random_events 为相关战场事件
  - [x] SubTask 1.4: 验证配置更新后无语法错误

- [x] Task 2: 更新 simulation_data.py 数据生成逻辑
  - [x] SubTask 2.1: 更新 generate_simulation_data 函数使用新交战方
  - [x] SubTask 2.2: 更新兵种生成逻辑（美军、以色列、伊朗、黎巴嫩等）
  - [x] SubTask 2.3: 更新武器系统生成逻辑（导弹、无人机、坦克等）
  - [x] SubTask 2.4: 更新民用设施生成逻辑
  - [x] SubTask 2.5: 验证数据生成完整性

- [x] Task 3: 更新 simulation_data.json 模拟数据
  - [x] SubTask 3.1: 运行数据生成脚本生成新的 simulation_data.json
  - [x] SubTask 3.2: 验证 JSON 格式正确，包含所有实体类型

- [x] Task 4: 验证系统功能
  - [x] SubTask 4.1: 启动服务验证数据加载成功
  - [x] SubTask 4.2: 验证 /api/graph 返回正确的节点和关系
  - [x] SubTask 4.3: 测试指挥官打击推荐是否基于新数据
  - [x] SubTask 4.4: 验证力量对比分析使用新参战方

- [x] Task 5: 更新相关文档
  - [x] SubTask 5.1: TASK_BREAKDOWN.md 无需更新（无战场配置说明）
  - [x] SubTask 5.2: README.md 无需更新